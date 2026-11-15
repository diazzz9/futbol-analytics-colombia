# Fútbol Analytics Colombia

Plataforma de datos de punta a punta sobre la Liga BetPlay (2022–2026), con foco en Independiente Santa Fe:
ingesta → limpieza → PostgreSQL → API → modelo de predicción → dashboard.

**Dashboard:** https://claude.ai/artifact/6uU9ckysdcN94UKCSGq687

## Qué hace

| Capa | Archivo | Qué resuelve |
|---|---|---|
| Ingesta | `scripts/fetch_espn.py` | Descarga todos los partidos desde la API pública de ESPN |
| ETL | `src/etl.py` | Normaliza fases y horarios (hora de Bogotá), trata estadísticas faltantes y valida la calidad |
| Base de datos | `sql/schema.sql`, `src/load_db.py` | Esquema relacional con llaves foráneas, `CHECK`, índices y dos vistas analíticas |
| API | `api/main.py` | FastAPI de solo lectura: posiciones, partidos, goleadores y predicciones |
| Modelo | `src/model.py` | Regresión de Poisson con ataque/defensa por equipo, ventaja de local y decaimiento temporal |
| Dashboard | `src/build_dashboard_data.py` | Agregados que alimentan el dashboard |

## Datos

- 2.182 partidos, 25 equipos y 18.017 eventos (goles y tarjetas), del 20 de enero de 2022 al 14 de noviembre de 2026.
- Por partido: marcador, fase, estadio, asistencia, posesión, tiros, tiros al arco, córners, faltas y tarjetas.
- Decisiones de limpieza:
  - ESPN codifica las estadísticas faltantes como 0; el ETL las convierte en nulos (unos 35 partidos).
  - La asistencia 0 se trata como dato faltante (372 partidos).
  - ESPN usa el nombre actual de cada club: La Equidad aparece como Internacional de Bogotá en toda la serie.
  - En 13 partidos la lista de goles no cuadra con el marcador; el marcador oficial es la fuente de verdad.

## Modelo

Validación walk-forward sobre 620 partidos desde julio de 2025; el modelo se reentrena cada mes solo con el pasado.

| Modelo | Acierto | Log loss | Brier |
|---|---|---|---|
| Frecuencias históricas | 46,6 % | 1,059 | 0,639 |
| Elo | 47,6 % | 1,044 | 0,623 |
| **Poisson (este proyecto)** | **49,8 %** | **1,014** | **0,608** |

La ventaja de local multiplica los goles esperados por 1,42. El modelo no conoce lesiones, sanciones ni nóminas.

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/fetch_espn.py        # opcional: actualiza los datos crudos
python src/etl.py                   # data/raw -> data/processed
python src/model.py                 # métricas y predicciones

docker compose up -d db             # PostgreSQL 16 en localhost:5432
python src/load_db.py               # crea el esquema y carga las tablas
uvicorn api.main:app --reload       # documentación en http://localhost:8000/docs
pytest -q                           # pruebas de la API
```

`DATABASE_URL` cambia la conexión (por defecto `postgresql+psycopg2://futbol:futbol@localhost:5432/futbol`).

## Endpoints

| Ruta | Descripción |
|---|---|
| `GET /standings?season=2026&tournament=Clausura` | Tabla de posiciones del todos contra todos |
| `GET /teams?q=santa` | Búsqueda de equipos |
| `GET /teams/{id}/matches` | Últimos partidos de un equipo |
| `GET /teams/{id}/summary` | Resumen por torneo: puntos, goles, posesión, tiros |
| `GET /scorers?season=2025&team_id=5488` | Goleadores |
| `GET /predict?home_id=5488&away_id=5484` | Probabilidades de local, empate y visitante |

## Ejemplo de SQL

```sql
SELECT name, pj, pts, dg
FROM v_standings
WHERE season = 2026 AND tournament = 'Clausura'
ORDER BY pts DESC, dg DESC, gf DESC;
```

## Próximos pasos

- Goles esperados (xG) a partir de tiros y tiros al arco.
- Orquestar la actualización diaria con cron o Airflow.
- Desplegar la API (Render o Fly.io) y conectar el dashboard en vivo.

Autor: Daniel Julián Díaz Riaño · [GitHub](https://github.com/diazzz9) · [LinkedIn](https://linkedin.com/in/daniel-diaz-a93143344)
