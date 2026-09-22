# Sistema de Recordatorios Automáticos de Eventos

## Descripción General

Se ha implementado un sistema completo de recordatorios automáticos que envía notificaciones a los usuarios cuando se registran en un evento. Hay 3 tipos de recordatorios que se envían automáticamente:

1. **Recordatorio Inmediato**: Se envía en el momento del registro
2. **Recordatorio 1 Día Antes**: Se envía exactamente 1 día antes del evento  
3. **Recordatorio 1 Hora Antes**: Se envía exactamente 1 hora antes del evento

## Características

✓ Los recordatorios aparecen en la sección **NOTIFICACIONES** del usuario  
✓ Tienen un diseño visual diferente (color naranja) para destacar  
✓ Un botón "✓ Recordado" permite cerrarlos  
✓ Se almacenan automáticamente en la base de datos  
✓ Pueden procesarse de forma automática mediante un scheduler  

## Cambios Realizados

### 1. Base de Datos

Se creó una nueva tabla `recordatorios_eventos`:

```sql
CREATE TABLE recordatorios_eventos (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  usuario_id INT UNSIGNED NOT NULL,
  evento_id INT UNSIGNED NOT NULL,
  tipo VARCHAR(50) NOT NULL,
  mensaje TEXT NOT NULL,
  fecha_programada DATETIME NOT NULL,
  enviado TINYINT(1) DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_usuario (usuario_id),
  KEY idx_evento (evento_id),
  KEY idx_fecha_programada (fecha_programada),
  KEY idx_enviado (enviado),
  FOREIGN KEY (usuario_id) REFERENCES user(id) ON DELETE CASCADE,
  FOREIGN KEY (evento_id) REFERENCES event(id) ON DELETE CASCADE
)
```

### 2. Backend (Flask)

Se agregaron las siguientes funciones en `app.py`:

#### `create_event_reminders(usuario_id, evento_id, evento_titulo, evento_fecha, evento_hora)`
Crea los 3 recordatorios automáticos cuando un usuario se registra en un evento:
- Recordatorio inmediato (fecha_programada = NOW())
- Recordatorio 1 día antes (fecha_programada = fecha_evento - 1 day)
- Recordatorio 1 hora antes (fecha_programada = fecha_evento - 1 hour)

#### `process_pending_event_reminders()`
Procesa todos los recordatorios cuya `fecha_programada` ha llegado:
- Busca recordatorios no enviados (`enviado = 0`)
- Crea una notificación en `mensajes_organizador` con el mensaje del recordatorio
- Marca el recordatorio como enviado (`enviado = 1`)

#### Ruta: `/api/procesar-recordatorios`
Ruta GET/POST que permite procesar recordatorios de forma manual:
```
GET /api/procesar-recordatorios
POST /api/procesar-recordatorios
```
Respuesta JSON:
```json
{
  "success": true,
  "message": "Se procesaron X recordatorios pendientes",
  "records_processed": X
}
```

#### Ruta: `/notificacion/<mensaje_id>/marcar-leida` (POST)
Marca un recordatorio como leído cuando el usuario hace clic en "✓ Recordado"

### 3. Frontend (Template)

Se actualizó `notificaciones.html`:

- Nuevos estilos CSS para recordatorios (clase `.notificacion.recordatorio`)
- Color naranja (#ff6f00) para diferenciar recordatorios
- Badge especial "RECORDATORIO" en naranja
- Icono de reloj (⏰) en el avatar del recordatorio
- Botón "✓ Recordado" para cerrar/marcar como leído

## Cómo Usar

### Procesamiento Manual

Puedes procesar los recordatorios manualmente visitando:
```
http://localhost:5000/api/procesar-recordatorios
```

O usando curl:
```bash
curl http://localhost:5000/api/procesar-recordatorios
```

### Procesamiento Automático (Recomendado)

Para procesar los recordatorios automáticamente, configura un cron job:

#### En Linux/macOS:

Edita el crontab:
```bash
crontab -e
```

Agrega una de estas líneas:

**Cada minuto:**
```
* * * * * cd /ruta/al/proyecto && python3 src/process_reminders.py
```

**Cada 5 minutos:**
```
*/5 * * * * cd /ruta/al/proyecto && python3 src/process_reminders.py
```

**Cada 10 minutos:**
```
*/10 * * * * cd /ruta/al/proyecto && python3 src/process_reminders.py
```

#### En Windows:

Usa el Programador de tareas de Windows para ejecutar:
```
python.exe C:\ruta\al\proyecto\src\process_reminders.py
```

### Script Standalone

Puedes ejecutar el script manualmente en cualquier momento:
```bash
python3 src/process_reminders.py
```

## Flujo Completo

1. **Usuario se registra en un evento**
   - Se ejecuta la ruta `/evento/registrar/<evento_id>`
   - Se crea el registro en la tabla `registrados`
   - Se genera el código QR
   - **Se llama a `create_event_reminders()`** ← Se crean los 3 recordatorios

2. **Se procesan los recordatorios (automático o manual)**
   - Se ejecuta `process_pending_event_reminders()`
   - Se buscan recordatorios con `fecha_programada <= NOW()`
   - Para cada recordatorio pendiente:
     - Se crea una notificación en `mensajes_organizador`
     - Se marca el recordatorio como enviado

3. **Usuario ve las notificaciones**
   - Accede a `/mis-notificaciones`
   - Ve los recordatorios con estilo naranja
   - Puede hacer clic en "✓ Recordado" para cerrar

## Ejemplos de Mensajes

### Recordatorio Inmediato
```
RECORDATORIO: El evento Concierto de Rock comienza en 15/12/2024 a las 20:00
```

### Recordatorio 1 Día Antes
```
RECORDATORIO: El evento Concierto de Rock comienza mañana 15/12/2024 a las 20:00
```

### Recordatorio 1 Hora Antes
```
RECORDATORIO: El evento Concierto de Rock comienza en 1 hora (a las 20:00)
```

## Estructura de Datos

### Tabla: recordatorios_eventos
```
┌─────────────────────────────────────────────────────────────────┐
│ id (PK) │ usuario_id │ evento_id │ tipo │ mensaje │ fecha_prog │
├─────────────────────────────────────────────────────────────────┤
│ 1       │ 5          │ 12        │ inmediato    │ RECORDATORIO │ 
│ 2       │ 5          │ 12        │ 1_dia_antes  │ RECORDATORIO │
│ 3       │ 5          │ 12        │ 1_hora_antes │ RECORDATORIO │
└─────────────────────────────────────────────────────────────────┘
```

### Tabla: mensajes_organizador (modificada)
Se utilizará esta tabla existente para almacenar las notificaciones de recordatorios cuando se procesan.

```sql
-- Ejemplo de recordatorio en mensajes_organizador después de procesarse:
INSERT INTO mensajes_organizador 
  (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
VALUES 
  (5, NULL, 12, 'RECORDATORIO', 'RECORDATORIO: El evento ... comienza ...', 0)
```

## Troubleshooting

### Los recordatorios no aparecen
1. Verifica que la tabla `recordatorios_eventos` existe
2. Ejecuta manualmente: `curl http://localhost:5000/api/procesar-recordatorios`
3. Revisa los logs de Flask para ver errores

### El cron job no funciona
1. Verifica la ruta correcta del proyecto
2. Intenta ejecutar el script manualmente: `python3 /ruta/al/proyecto/src/process_reminders.py`
3. Revisa los logs del cron: `grep CRON /var/log/syslog`

### Los recordatorios aparecen con retraso
- Aumenta la frecuencia del cron job (de cada 10 min a cada 5 min)
- O procesa manualmente más frecuentemente

## Consideraciones de Rendimiento

- La tabla `recordatorios_eventos` se indexa por `fecha_programada` para búsquedas rápidas
- Al procesar, se limita a 100 recordatorios por llamada para evitar sobrecargar
- Los recordatorios se eliminan automáticamente cuando se elimina el usuario o evento

## Seguridad

La ruta `/api/procesar-recordatorios` está abierta (sin login requerido) para facilitar llamadas de schedulers externos. Si deseas agregar autenticación:

1. Génera un token secreto
2. Modifica la función `procesar_recordatorios()` para validar el token
3. Pasa el token como parámetro: `/api/procesar-recordatorios?token=tu_token_secreto`

## Próximas Mejoras (Opcional)

- [ ] Agregar notificaciones por email
- [ ] Permitir personalización de horarios de recordatorios
- [ ] Dashboard de visualización de recordatorios procesados
- [ ] Cancelación de recordatorios cuando se desregistra del evento
- [ ] Sistema de "snooze" (posponer recordatorio)

---

**Creado:** Septiembre 2026  
**Última actualización:** Septiembre 2026
