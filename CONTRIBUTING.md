# Contribuir a Atlify

Atlify separa extracción determinista, interpretación del agente y validación.
Preservá esa separación: una referencia correcta no prueba una conclusión.

## Entorno y pruebas

Para usar el skill: Python 3.10+, Git y un agente que ejecute comandos.
Para las pruebas de navegador: Node.js y Chromium de Playwright. CI usa Node 24.

Desde la raíz:

```sh
python3 scripts/atlify.py doctor
python3 -m unittest discover -s evals -p 'test_*.py'
python3 scripts/release.py --check
```

Para el visor y la landing:

```sh
cd evals/e2e
npm ci
npx playwright install chromium
npm test
```

En un runner Linux sin librerías de sistema, `npx playwright install --with-deps chromium`
instala también los requisitos del navegador. Playwright usa un solo worker;
reservá los puertos 4173/4174 y no ejecutes dos suites al mismo tiempo.
El fixture es sintético: **no inicies su aplicación** ni lo uses en producción.
Los tests del instalador usan un HOME temporal, no tus carpetas de agentes.

## Sincronizar demos y capturas

Al cambiar `assets/visor.html`, los scripts o el fixture:

```sh
python3 scripts/release.py
(cd evals/e2e && ATLIFY_CAPTURE=1 npx playwright test release-captures.spec.ts --project=escritorio)
python3 scripts/release.py --check
```

`release.py` genera el inventario en un temporal, valida y reconstruye las dos demos
públicas, y copia las fuentes con sus licencias. Solo usa `evals/fixtures/pet-care-api`.
`--check` no modifica `docs/`: falla cuando las demos o las fuentes están desactualizadas.
La comparación descomprime el contenido fuente para no confundir diferencias de
Python/zlib con cambios del producto. El build fija el timestamp gzip en cero.

Las capturas se regeneran **solo con opt-in**. La suite normal no pisa imágenes.
`release-captures.spec.ts` genera las vistas reales, el ejemplo móvil y la portada
social de 1200×630 a partir de `docs/social-card.html`. Revisalas visualmente;
`release.py --check` no detecta capturas viejas.

Para revisar la landing localmente:

```sh
python3 -m http.server 4318 --bind 127.0.0.1 --directory docs
```

Abrí `http://127.0.0.1:4318`. No necesita bundler, backend ni servicios externos.
La landing funciona sin JS; el explorador de capturas, selector de agente y botones
para copiar son mejoras progresivas. Usá Archivo, Archivo Black y el verde `#183e32`.

## Qué verifica cada prueba

- **Python:** extractor, validador, builder, instalador aislado, enlaces locales,
  metadatos sociales, assets y vigencia de demos.
- **Navegador:** visor y landing, responsive, texto al 200%, teclado, portapapeles
  (éxito y error), contenido sin JS y demo descargada sin conexión.
- **Comportamiento del agente:** `evals/cases.json`. Requiere correr el skill en un
  agente. No se considera cubierto por pasar los tests deterministas.
- **Publicación real:** requiere revisar la URL desplegada; no queda probada por CI.

Los tests móviles emulan un dispositivo en Chromium; no son pruebas en Safari/iOS físico.
CI usa las acciones oficiales [checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python) y
[setup-node](https://github.com/actions/setup-node), con permisos de solo lectura.
No publica, no crea tags y no evalúa modelos pagos.

## Cambios acotados

Agregá un caso mínimo para cada bug. No incluyas repos privados, credenciales ni
capturas de clientes. Conservá los nombres del esquema (`naciones`, `hallazgos`, etc.)
y el contrato de escrituras en `.atlify/`. No mezcles un arreglo del extractor con
un rediseño del visor. Si cambia una capacidad, actualizá la landing y ambos README.

### Scroll narrativo de la landing

`docs/site.js` usa GSAP/ScrollTrigger 3.15.0 locales para fijar la escena del atlas
mientras cambian sus cuatro vistas. No intercepta rueda/touch ni reemplaza el scroll
nativo. Móvil, pantallas bajas, texto ampliado, movimiento reducido y ausencia de
JS conservan el flujo normal. La prueba ScrollTrigger verifica pin, fases y teardown.
La licencia de GSAP es independiente de MIT; ver `docs/vendor/gsap/NOTICE.txt`.
