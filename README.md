# Fútbol Analytics Colombia

Plataforma de datos de punta a punta sobre la Liga BetPlay (2022–2026):
ingesta → limpieza → PostgreSQL → API → modelo de predicción → simulación del título → dashboard.

**API en vivo:** https://futbol-analytics-colombia.onrender.com/docs (el plan gratuito tarda cerca de un minuto en despertar)

**Dashboard:** https://claude.ai/artifact/6uU9ckysdcN94UKCSGq687

![Probabilidad de llegar a la final y de ser campeón](docs/simulacion.png)

## Qué hace

| Capa | Archivo | Qué resuelve |
|---|---|---|
| Ingesta | `scripts/fetch_espn.py` | Descarga todos los partidos desde la API pública de ESPN |
| ETL | `src/etl.py` | Normaliza fases y horarios (hora de Bogotá), trata estadísticas faltantes y valida la calidad |
| Base de datos | `sql/schema.sql`, `src/load_db.py` | Esquema relacional con llaves foráneas, `CHECK`, índices y dos vistas analíticas |
| API | `api/main.py` | FastAPI de solo lectura: posiciones, partidos, goleadores, predicciones y simulación |
| Modelo | `src/model.py` | Regresión de Poisson con ataque/defensa por equipo, ventaja de local y decaimiento temporal |
| Simulación | `src/simulate.py` | Monte Carlo de los cuadrangulares y la final con las reglas reales del torneo |
| Dashboard | `src/build_dashboard_data.py` | Agregados por equipo que alimentan el dashboard |
| Automatización | `.github/workflows/actualizar.yml` | Actualiza datos, modelo y simulación todos los días y corre las pruebas |

## Datos

- 2.182 partidos, 25 equipos y 18.017 eventos (goles y tarjetas), del 20 de enero de 2022 al 14 de noviembre de 2026.
- Por partido: marcador, fase, estadio, asistencia, posesión, tiros, tiros al arco, córners, faltas y tarjetas.
- Decisiones de limpieza:
  - ESPN codifica las estadísticas faltantes como 0; el ETL las convierte en nulos (35 partidos).
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

## Simulación del Clausura 2026

20.000 simulaciones de los cuadrangulares y la final, antes de que se juegue la primera fecha:

| Equipo | Grupo | Llega a la final | Campeón |
|---|---|---|---|
| Atlético Nacional ★ | A | 49,6 % | 29,7 % |
| América de Cali ★ | B | 38,1 % | 19,3 % |
| Millonarios | B | 25,1 % | 11,5 % |
| Atlético Bucaramanga | B | 23,4 % | 10,8 % |
| Independiente Santa Fe | A | 21,2 % | 10,3 % |
| Independiente Medellín | A | 18,1 % | 8,5 % |
| Deportivo Cali | B | 13,3 % | 5,2 % |
| Once Caldas | A | 11,1 % | 4,5 % |

Reglas modeladas:

- Dos grupos de cuatro a ida y vuelta; el primero de cada grupo va a la final.
- ★ Cabezas de serie con punto invisible: ganan cualquier empate en puntos. Sin cabeza de serie involucrado deciden
  diferencia de gol, goles a favor y goles de visitante.
- Final a ida y vuelta; cierra de local el mejor del todos contra todos. Un empate global se define por penales (50/50).
- Los partidos de cuadrangulares ya jugados entran con su resultado real; solo se simula lo pendiente.

Los grupos se configuran en `data/config/cuadrangulares.json`. Entre dos semillas distintas, los porcentajes
cambian menos de un punto.

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/fetch_espn.py         # opcional: actualiza los datos crudos
python src/etl.py                    # data/raw -> data/processed
python src/model.py                  # métricas y predicciones
python src/simulate.py               # probabilidades de final y título
python src/build_dashboard_data.py   # agregados del dashboard
python src/make_figure.py            # imagen del README

docker compose up -d db              # PostgreSQL 16 en localhost:5432
python src/load_db.py                # crea el esquema y carga las tablas
uvicorn api.main:app --reload        # documentación en http://localhost:8000/docs
pytest -q                            # 10 pruebas: ETL, modelo y API
```

`DATABASE_URL` cambia la conexión (por defecto `postgresql+psycopg2://futbol:futbol@localhost:5432/futbol`).
Con `DATABASE_URL=sqlite:///futbol.db` todo corre sin Docker.

## Endpoints

| Ruta | Descripción |
|---|---|
| `GET /standings?season=2026&tournament=Clausura` | Tabla de posiciones del todos contra todos |
| `GET /simulation` | Probabilidad de final y de título de cada equipo |
| `GET /teams?q=santa` | Búsqueda de equipos |
| `GET /teams/{id}/matches` | Últimos partidos de un equipo |
| `GET /teams/{id}/summary` | Resumen por torneo: puntos, goles, posesión, tiros |
| `GET /scorers?season=2025&team_id=5488` | Goleadores |
| `GET /predict?home_id=5488&away_id=5484` | Probabilidades de local, empate y visitante |

## Despliegue y automatización

- **API pública:** `Dockerfile` y `render.yaml` despliegan la API en Render, en https://futbol-analytics-colombia.onrender.com. La imagen construye una base SQLite con
  los datos del repositorio, así que no necesita un servidor de base de datos; en local se usa PostgreSQL.
- **Actualización diaria:** el flujo de GitHub Actions descarga los partidos nuevos, reejecuta ETL, modelo y
  simulación, corre las pruebas y guarda los cambios. Con Render en despliegue automático, cada actualización
  publica la API con datos frescos.

## Próximos pasos

- Goles esperados (xG) a partir de tiros y tiros al arco.
- Conectar el dashboard a la API desplegada para que se actualice solo.

Autor: Daniel Julián Díaz Riaño · [GitHub](https://github.com/diazzz9) · [LinkedIn](https://linkedin.com/in/daniel-diaz-a93143344)
