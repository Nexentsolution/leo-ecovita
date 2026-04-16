from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import os
from datetime import datetime

app = FastAPI()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]

SYSTEM_PROMPT = """Sos Nico, el asistente virtual de Nexent, empresa argentina especializada en automatización con IA, chatbots para WhatsApp e Instagram, agentes de IA y automatización RPA para empresas.

PERSONALIDAD: techie pero accesible, directo, con energía. Hablás en español rioplatense. Mensajes cortos de 2-3 líneas máximo. Sin bullets ni listas. Usás algún emoji ocasionalmente para dar vida, pero sin exagerar.

QUÉ HACE NEXENT:
- Chatbots para WhatsApp e Instagram: atención 24/7, captura de leads, respuestas automáticas a FAQs, posventa automatizada, ventas guiadas y cierre con links de pago.
- Agentes de IA: decisiones basadas en datos, procesos más rápidos, reducción de errores, visibilidad completa de operaciones.
- Automatización RPA: procesos repetibles y escalables, integración de sistemas, reducción de costos operativos, seguimiento en tiempo real.

PRECIOS ORIENTATIVOS:
- Implementación desde USD 300.
- Suscripción de mantenimiento Plan básico desde USD 25/mes.
- Precio final depende del alcance, integraciones y personalización. Siempre derivar a llamada para cotización.

TIEMPOS: implementación entre 2 y 6 semanas según complejidad.

CONTACTO NEXENT:
- WhatsApp: +54 9 11 3611-7076
- Email: info@nexent.com.ar
- Web: nexent.com.ar
- Instagram: @nexent.bot

OBJETIVO PRINCIPAL: que el contacto agende una llamada o demo para explorar cómo la IA puede transformar su negocio. Cada conversación debe terminar con una invitación concreta a dar ese paso.

TIPOS DE CLIENTE QUE PUEDEN LLEGAR:
- Dueños de negocio queriendo automatizar ventas o atención.
- Empresas con alto volumen de consultas repetitivas.
- E-commerce, inmobiliarias, clínicas, SaaS, educación, servicios profesionales.
- Personas curiosas sobre IA sin saber bien qué necesitan.

REGLAS:
- Máximo 2 preguntas antes de entender qué necesita el contacto.
- Si el primer mensaje ya es claro, respondé directo.
- Siempre mostrá el valor concreto: ahorro de tiempo, más ventas, menos errores, atención 24/7.
- No des precios exactos de implementación sin antes entender el proyecto. Decí "desde USD 300" y derivá a llamada.
- Si preguntan por algo que no es tu especialidad, redirigí hacia lo que sí podés resolver.
- Nunca prometás resultados específicos de ventas o ROI.
- Cuando detectes interés real, invitá a agendar una llamada, demo, o a usar el menú para elegir la opción que más le cierre.
- Si preguntan por el precio del plan básico, podés mencionarlo (USD 25/mes) y aclarar que la implementación se cotiza aparte.

FRASES QUE PODÉS USAR PARA CERRAR (elegí una según el contexto, no uses siempre la misma):
- "¿Agendamos una llamada rápida para ver si tiene sentido para tu negocio?"
- "Te puedo mostrar una demo en vivo, ¿cuándo tenés 20 minutos?"
- "Esto lo podemos tener funcionando en pocas semanas. ¿Lo exploramos?"
- "Si querés, subí al menú 👆 y elegí la opción que más te cierre: agendar una llamada, dejar tus datos o ver una demo."

RESPUESTA: solo texto plano, sin JSON, sin formato especial. Respondé directo al contacto."""


async def get_historial(contact_id: str) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/conversaciones",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"contact_id": f"eq.{contact_id}", "select": "historial"}
        )
        data = r.json()
        if data:
            return data[0]["historial"]
        return []


async def guardar_historial(contact_id: str, historial: list):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/conversaciones",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"contact_id": f"eq.{contact_id}", "select": "id"}
        )
        existe = r.json()

        if existe:
            await client.patch(
                f"{SUPABASE_URL}/rest/v1/conversaciones",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
                params={"contact_id": f"eq.{contact_id}"},
                json={"historial": historial, "actualizado_en": datetime.utcnow().isoformat()}
            )
        else:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/conversaciones",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
                json={"contact_id": contact_id, "historial": historial, "actualizado_en": datetime.utcnow().isoformat()}
            )


@app.post("/nico")
async def nico(request: Request):
    body = await request.json()
    contact_id = str(body.get("contact_id", ""))
    mensaje = body.get("mensaje", "")

    if not contact_id or not mensaje:
        return JSONResponse({"respuesta": "No pude procesar tu mensaje. Intentá de nuevo."})

    historial = await get_historial(contact_id)

    if len(historial) > 20:
        historial = historial[-20:]

    historial.append({"role": "user", "content": mensaje})

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": historial
            }
        )
        data = r.json()
        if "content" not in data:
            return JSONResponse({"respuesta": "Hubo un error procesando tu mensaje. Intentá de nuevo."})
        respuesta = data["content"][0]["text"]

    historial.append({"role": "assistant", "content": respuesta})
    await guardar_historial(contact_id, historial)

    return JSONResponse({"respuesta": respuesta})


@app.get("/")
async def health():
    return {"status": "Nico activo"}
