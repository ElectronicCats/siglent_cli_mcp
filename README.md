# osc — CLI para el osciloscopio Siglent SDS1104X-E

Control completo por línea de comandos de un osciloscopio **Siglent SDS1104X-E**
(SDS1104X-E / SDS1204X-E, serie 1000X-E) a través de **USB (USBTMC)**.

> **Importante:** este firmware **NO habla el SCPI estándar de Siglent**, sino un
> dialecto **LeCroy X-Stream** (comandos como `C1:VDIV`, `TDIV`, `C1:PAVA?`).
> Este CLI está escrito específicamente para ese dialecto, descubierto y
> verificado contra el dispositivo real (firmware `8.1.6.1.37R2`).

## Instalación

```bash
cd osc
python3 -m venv .venv
.venv/bin/pip install -e .
```

Dependencias: `click`, `pyvisa`, `pyvisa-py`, `pyusb` (se instalan automáticamente).
No se necesita NI-VISA (usa el backend `pyvisa-py` + libusb).

### Acceso al dispositivo USB (una sola vez)

El osciloscopio se expone como USBTMC (`/dev/usbtmc0`), accesible solo por root
por defecto. Para usarlo sin sudo:

```bash
sudo ./install-udev.sh
```

Esta regla da permisos al grupo `plugdev` para el VID/PID de Siglent
(`f4ec:ee38`). Tras instalarla, desenchufa y vuelve a enchufar el USB del
osciloscopio (o ejecuta `sudo udevadm trigger`).

## Uso

```bash
osc --help                 # ayuda general
osc <comando> --help       # ayuda de cada grupo
```

La conexión se detecta automáticamente. Puedes forzar una conexión explícita
con `-r USB0::0xF4EC::0xEE38::<serial>::0::INSTR`.

### Grupos de comandos

| Grupo | Descripción |
|-------|-------------|
| `system`  | Identidad (`*IDN?`), reset, errores, reloj, self-test, calibración |
| `channel` | Canales CH1–CH4: v/div, offset, acoplamiento, BW, sonda, inversión, skew |
| `timebase`| Escala horizontal, delay, sample rate, memoria, promedios |
| `trigger` | Modo, tipo, fuente, nivel, acoplamiento |
| `measure` | Mediciones automáticas (Vpp, freq, RMS, mean, period, …) |
| `math`    | Canal matemático |
| `cursor`  | Cursores |
| `display` | Rejilla, intensidad, menú |
| `waveform`| **Captura de datos de forma de onda** (CSV) |
| `screen`  | **Captura de pantalla** (BMP) |
| `decode`  | Disparo serie UART / I2C / SPI y **extracción de bytes** (`uart-bytes`, `i2c-bytes`, `spi-bytes`) |
| `counter` | Contador de frecuencia |
| `awg`     | Generador de ondas (AWG): onda base, burst, sweep, arbitraria |
| `save`    | Guardar/recuperar configuración |
| `raw`     | Enviar cualquier comando arbitrario |

### Ejemplos

```bash
osc system idn
osc channel list
osc channel vdiv --channel 1 0.5
osc trigger mode NORM
osc measure vpp --source C1
osc measure all --source C1

# Capturar forma de onda a CSV (voltaje y tiempo reales)
osc waveform capture --source C1 --points 1000 --output onda.csv

# Capturar pantalla a BMP
osc screen capture --output pantalla.bmp

# Generador de ondas (AWG)
osc awg set --wave SINE --freq 1000 --amp 4 --on
osc awg freq 5000
osc awg arb StairUp
osc awg burst --on --cycles 10
osc awg sweep --start 100 --stop 1000 --time 1

# Extraer bytes de un bus serie (decode por software)
osc decode uart-bytes --rx C1 --baud 9600
osc decode i2c-bytes --scl C1 --sda C2
osc decode spi-bytes --clk C1 --mosi C2 --cs C4

# Comando arbitrario
osc raw "C1:PAVA? PKPK"
```

## Notas de implementación

- **Dialecto LeCroy X-Stream**: las respuestas incluyen cabecera corta
  (p. ej. `C1:VDIV 1.00E+00V`). Usar `CHDR OFF` para datos binarios.
- **Mediciones**: `C<n>:PAVA? <parámetro>` (no `MEASure`). Parámetros
  verificados: `PKPK, MAX, MIN, TOP, BASE, AMPL, MEAN, RMS, PER, FREQ, RISE,
  FALL, WID, DUTY, OVSN, FPRE, CMEAN, CRMS`.
- **Forma de onda**: `C<n>:WF? ALL` devuelve un bloque IEEE 488.2
  (`#9<longitud><datos>`) con un descriptor WAVEDESC de 346 bytes. El campo
  `VERTICAL_GAIN` (offset 156) almacena **V/div**, y los datos son códigos ADC
  de 8 bits con signo que abarcan la rejilla de 8 divisiones:
  `voltaje = código × vdiv / 32`. El parámetro `NP` (número de puntos) es
  ignorado por este firmware: siempre devuelve la memoria completa (puede ser
  1.4M puntos). La lectura se hace en bucle hasta completar la longitud
  declarada en el bloque.
- **Pantalla**: `SCDP` devuelve un BMP raw de 800×480.
- **Decodificación serie**: `TRIG_UART:`, `TRIG_IIC:` (I2C), `TRIG_SPI:`.
- **Contador**: `FCNT` (no `COUNTER`).
- **Reloj**: `SYST:DATE` / `SYST:TIME` (no `DATE`/`TIME`).

## Solución de problemas

- **"No USBTMC device found"**: osciloscopio apagado o regla udev no aplicada.
  Verifica `lsusb | grep -i siglent` y `ls -l /dev/usbtmc0`.
- **El osciloscopio no responde (timeouts)**: si has hecho muchos resets USB
  (`dev.reset()`), el firmware puede quedar bloqueado. **Apaga y enciende el
  osciloscopio físicamente** (no basta con replugar el USB).

## Tests

Tests offline: `python tests/test_decoders.py`.

## Licencia

MIT
