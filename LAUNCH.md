# Kit de lanzamiento de Atlify

**Publicación autorizada el 2 de noviembre de 2026.** Repositorio público:
https://github.com/miguelecf/atlify. Landing publicada y verificada: https://miguelecf.github.io/atlify/ (GitHub Pages,
`main` y `/docs`). No se publicaron posts en LinkedIn ni se modificó el portfolio.

La tabla siguiente conserva el estado **anterior** al lanzamiento; los comandos
son una guía de mantenimiento, no una instrucción para volver a crear el repo.

## Estado comprobado el 2 de noviembre de 2026

| Parte | Estado |
| --- | --- |
| Cuenta consultada con GitHub CLI | `miguelecf` |
| `miguelecf/atlify` | GitHub no lo resuelve con esta cuenta; no se encontró en su listado de repos |
| Landing prevista | `https://miguelecf.github.io/atlify/` responde HTTP 404 |
| Git local | Rama `main`, sin remote, con cambios de esta y anteriores etapas sin commit |
| Landing, demos y portada social | Preparadas localmente en `docs/` |
| Portfolio y LinkedIn | Sin modificar; textos listos más abajo |

No confundir archivos listos con un producto publicado. Los comandos siguientes
son instrucciones para el lanzamiento: **no se ejecutaron en esta preparación**.

## Publicar, paso a paso

### 1. Revisar y validar

Desde la raíz del proyecto, revisar también archivos nuevos (no aparecen en `git diff`):

```sh
git status --short
git diff --check
git diff
python3 scripts/atlify.py doctor
python3 -m unittest discover -s evals -p 'test_*.py'
python3 scripts/release.py --check
(cd evals/e2e && npm ci && npx playwright install chromium && npm test)
```

No publicar `node_modules`, trazas, credenciales ni atlas de repos privados.
La demo pública contiene deliberadamente código inseguro del fixture sintético:
no es una aplicación para desplegar. Revisar todo el historial antes de hacerlo público.

### 2. Crear el repo y subir (requiere autorización)

Si sigue sin existir `miguelecf/atlify`, y una vez revisados los archivos:

```sh
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Prepare Atlify 1.1 for public launch"
gh repo create miguelecf/atlify --public --source=. --remote=origin --description "An offline, code-linked atlas for HTTP API repositories. A skill by Miguel Caraballo."
git push -u origin main
```

`--public` expone los archivos y el historial subidos. Si el repositorio ya existe,
no repetir la creación: confirmar primero propietario, contenido y remoto.
No usar `--force`. No se crea un tag hasta validar CI y el sitio público.

### 3. Activar la landing

En GitHub: **Settings → Pages → Deploy from a branch → main → /docs → Save**.
Esperar a que finalice el deployment. `docs/.nojekyll` y las rutas relativas ya
están preparados. No hace falta instalar dependencias para servir la landing.

Comprobar desde un navegador y sin sesión:

- Landing: `https://miguelecf.github.io/atlify/`.
- Demo completa: `https://miguelecf.github.io/atlify/demo/atlas.html`.
- Demo endpoint: `https://miguelecf.github.io/atlify/demo/foco.html`.
- Portada: `https://miguelecf.github.io/atlify/img/og-atlify.png`.
- Clonado e instalación desde un directorio temporal, sin tocar skills existentes.

La CI solo valida: Pages desde rama no queda bloqueado automáticamente por ella.
Cuando todo pase, cambiar el aviso inicial de ambos README a «Publicado», actualizar
esta tabla y recién entonces crear una release/tag y compartir los enlaces.

### 4. Presentarlo

Usar la portada social y el borrador de abajo. Revisar la vista previa de LinkedIn
antes de enviar. La ficha del portfolio se integra por separado en su checkout;
este proyecto no modifica ese sitio. No publicar el HTML de un repo privado como ejemplo.

## La idea en una frase

**Atlify: entendé el repo antes de tocarlo.**

Un skill para agentes de código que convierte un repo con API HTTP en un atlas
interactivo: mapa del sistema, recorridos de endpoints y hallazgos con referencias
al código real. El resultado es un único HTML que funciona offline.

## Texto para LinkedIn

Borrador en primera persona; revisar y usar después de comprobar el despliegue:

---

Que un repo funcione no significa que lo entiendas.

Podés encontrar la pantalla, el endpoint y la tabla. Lo difícil es reconstruir qué
pasa entre las tres y qué más depende de eso cuando necesitás cambiar algo.

Para trabajar sobre ese problema hice Atlify, un skill para agentes de código.

Le pedís el atlas de un repo con API y genera un HTML interactivo con el mapa del
sistema, el recorrido de cada endpoint y los problemas encontrados, vinculados a
archivos y símbolos del código real. También podés enfocarlo en un solo endpoint
para revisar funciones compartidas, tablas y referencias a tests antes de editar.

La decisión central fue separar el trabajo: scripts en Python para extraer y
validar referencias; el agente para leer, explicar y señalar problemas. El visor
funciona offline y el skill no aplica arreglos ni ejecuta la aplicación.

No pretende demostrar que el sistema es correcto ni reemplazar una revisión.
Busca que tengas más contexto para hacerla.

Dejé una demo con un repo de ejemplo y el código abierto bajo MIT. También incluí
un recorrido por la implementación para quien quiera construir sus propios skills.

Demo y cómo usarlo: https://miguelecf.github.io/atlify/
Código: https://github.com/miguelecf/atlify

¿En qué parte te cuesta más ubicarte cuando entrás a un repo nuevo?

#DesarrolloDeSoftware #OpenSource #AI

---

## Ficha para el portfolio

**Título:** Atlify — un atlas para entender el código.

**Descripción corta:** Skill para agentes de código que conecta pantallas,
endpoints y tablas en un HTML interactivo y offline. Incluye recorridos con
referencias al código, hallazgos y un modo de análisis de impacto por endpoint.

**Mi trabajo:** diseño del contrato del skill, scripts de extracción y validación,
visor interactivo, pruebas automatizadas y presentación pública del producto.

**Decisiones para destacar:**
- Separar hechos extraídos por scripts de interpretaciones del agente.
- Vincular el análisis a código navegable, en vez de entregar solo texto.
- Empaquetar el resultado en un archivo sin dependencias de red.
- Mantener el modo endpoint para cambios acotados en repos grandes.

**Tecnologías:** Python (biblioteca estándar), Preact + htm embebidos, HTML/CSS/JS,
Playwright. Agentes con soporte para `SKILL.md`.

**Botones:** «Ver Atlify» → landing; «Explorar demo» → `demo/atlas.html`;
«Ver código» → GitHub.

**Imágenes:**
- `docs/img/og-atlify.png`: portada de 1200×630 para redes y ficha.
- `docs/img/recorrido.png`: producto en uso; no es un mockup.
- `docs/img/foco.png`: análisis de impacto de un endpoint.
- `docs/img/celular.png`: vista móvil del visor.

Texto alternativo de la portada: «Atlify. Entendé el repo antes de tocarlo.
Pantalla, endpoint y tabla conectados en un atlas offline. Por Miguel Caraballo».

## Antes de publicar

- [ ] Revisar el diff completo: hay cambios de la etapa anterior sin commit.
- [ ] Confirmar nombre y propietario del repositorio remoto: `miguelecf/atlify`.
- [ ] Revisar que las demos y capturas contengan solo el fixture público.
- [ ] Revisar los cambios, crear el repo remoto si falta y autorizar commit/push.
- [ ] Confirmar que pasen las pruebas y CI (comandos en CONTRIBUTING.md).
- [ ] Configurar GitHub Pages con **Deploy from a branch**, rama `main`, carpeta `/docs`.
- [ ] Abrir la landing pública, ambas demos y la descarga desde la URL desplegada.
- [ ] Confirmar título, descripción y portada al pegar el enlace en una vista previa de LinkedIn.
- [ ] Integrar la ficha al portfolio y recién entonces publicar el post.

GitHub permite servir una carpeta `/docs` desde una rama: no hace falta agregar
un pipeline de build para esta landing estática. Ver la
[guía oficial de configuración de Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
El workflow de este repo solo valida; **no** controla ni bloquea por sí mismo el
despliegue desde rama. Configurá protecciones si querés exigir CI antes de mergear.

Si el nombre público cambia, actualizar URLs en `README*.md`, `SKILL.md`, esta guía
y los metadatos canonical/Open Graph/Twitter de `docs/index.html` antes de publicar.

## Qué no prometer

No afirmar que detecta todos los errores, soporta cualquier stack automáticamente,
prueba la seguridad del repo, ejecuta tests o garantiza cobertura. Los 11 hallazgos
son del fixture de demostración, no una tasa de detección medida para cualquier modelo.
El visor es offline; el análisis puede usar un proveedor de IA remoto.
El HTML embebe archivos fuente: compartirlo requiere revisar su contenido y permisos.

## Validación local de esta preparación

Comprobada el 28 de octubre de 2026 en macOS, Python 3.13.4 y Chromium de Playwright:

- 39 tests Python aprobados (incluye instalador con HOME temporal).
- 44 tests de navegador aprobados; 6 omitidos deliberadamente por dispositivo u opt-in de capturas.
- 1 prueba de regeneración de imágenes aprobada, ejecutada aparte con opt-in.
- Landing a 360, 768 y 1280 px, también con texto al 200%.
- Copiar, selector de agente, explorador de vistas, FAQ y contenido sin JavaScript.
- Demo descargada abierta desde `file://` sin red, con código fuente visible.
- `release.py --check`, `git diff --check`, sintaxis JS y shell: OK.
- Capturas de escritorio, móvil y portada social revisadas visualmente.

**No verificado:** ejecución en GitHub Actions, Python 3.10 en este equipo,
Safari/iOS físico, evals en agentes/modelos ni despliegue público. El workflow está
preparado; no se presenta como una ejecución de CI ya aprobada.

### Revalidación del 2 de noviembre de 2026

40 tests Python y 44 tests de navegador aprobados (6 skips deliberados).
`release.py --check` y `git diff --check`: OK. Revisadas capturas nuevas de la landing
en escritorio y móvil emulado. Se mantiene la identidad frontend-personal y se
ajusta el contenedor a 1180px. Acciones de CI fijadas a SHA verificados en GitHub.
Sigue pendiente crear el remoto, hacer commit/push autorizado, ejecutar CI remoto y
activar/verificar Pages. Ninguno de esos pasos se considera realizado por estas pruebas.


## Publicación completada — 2 de noviembre de 2026

- Código público: https://github.com/miguelecf/atlify, commit de lanzamiento `5acbe16`.
- Landing y ambas demos: HTTP 200 y apertura en Chromium público sin errores JS.
- Portada social: HTTP 200.
- GitHub Pages: build/deployment aprobado.
- CI del commit de lanzamiento: Python 3.10 y 3.13, vigencia de demos y navegador aprobados.
- Clonado desde GitHub e instalación comprobados con HOME temporal; doctor OK.
- La evidencia de publicación reemplaza los pendientes históricos de las secciones anteriores.
- No se modificó el portfolio ni se envió el borrador de LinkedIn.
