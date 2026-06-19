"""Traduce gaps de diseño a checklist de validación manual en DEV."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DEV_URL = "https://dev.doeventsapp.com"

AREA_ORDER = [
    "Autenticación",
    "Feed / Inicio",
    "Mi perfil",
    "Perfil de otros usuarios",
    "Historias y búsqueda",
    "Mapa y eventos",
    "Crear / publicar evento",
    "Detalle de evento",
    "Invitaciones y tickets",
    "Control de acceso",
    "Invitados",
    "Chat y mensajes",
    "Pagos y banca",
    "Servicios",
    "Asistente IA",
    "Panel admin",
    "Venues",
    "Layout / navegación",
    "Otros",
]

STATUS_LABEL = {
    "missing_in_web": "Falta implementar",
    "needs_adaptation": "Revisar empalme",
    "minor_drift": "Ajuste menor",
    "aligned": "Alineado",
}

# componente → área, dónde ir, qué validar
COMPONENT_HINTS: dict[str, dict[str, Any]] = {
    "ProfileView": {
        "area": "Mi perfil",
        "where": "Menú → Mi perfil",
        "checks": [
            "Layout general (avatar, nombre, bio, estadísticas)",
            "Tabs o secciones del perfil vs Lovable",
            "Accesos a galería, posts, eventos y favoritos",
        ],
    },
    "ProfileGallery": {
        "area": "Mi perfil",
        "where": "Mi perfil → Mi galería",
        "checks": [
            "Botón o enlace «Mi galería» visible y funcional",
            "Grid de fotos, estados vacío y cargando",
            "Subir/eliminar foto usando API real (sin mocks)",
        ],
    },
    "EditProfileView": {
        "area": "Mi perfil",
        "where": "Mi perfil → Editar perfil",
        "checks": [
            "Formulario de edición (nombre, bio, foto)",
            "Validaciones y botones guardar/cancelar",
            "Mensajes de éxito/error al guardar",
        ],
    },
    "ProfileCommentsView": {
        "area": "Mi perfil",
        "where": "Mi perfil → Comentarios",
        "checks": ["Lista de comentarios", "Estados vacío y paginación"],
    },
    "UserProfileView": {
        "area": "Perfil de otros usuarios",
        "where": "Feed → perfil de otro usuario",
        "checks": ["Vista de perfil ajeno", "Seguir/mensaje y tabs públicos"],
    },
    "FeedHero": {
        "area": "Feed / Inicio",
        "where": "Feed principal",
        "checks": ["Banner/hero superior", "CTA y copy vs Lovable"],
    },
    "FeedServicesCarousel": {
        "area": "Feed / Inicio",
        "where": "Feed → carrusel de servicios",
        "checks": ["Carrusel horizontal", "Cards y navegación"],
    },
    "PostCard": {
        "area": "Feed / Inicio",
        "where": "Feed → tarjeta de publicación",
        "checks": ["Diseño de post (media, likes, comentarios)", "Acciones del menú ⋮"],
    },
    "CreatePostSheet": {
        "area": "Feed / Inicio",
        "where": "Feed → crear publicación",
        "checks": ["Sheet/modal crear post", "Adjuntar media y publicar"],
    },
    "CommentsSheet": {
        "area": "Feed / Inicio",
        "where": "Post → comentarios",
        "checks": ["Sheet de comentarios", "Input y listado"],
    },
    "MapView": {
        "area": "Mapa y eventos",
        "where": "Feed → Mapa",
        "checks": ["Mapa interactivo", "Pins de eventos y filtros"],
    },
    "EventsView": {
        "area": "Mapa y eventos",
        "where": "Feed → Eventos",
        "checks": ["Listado/grid de eventos", "Filtros y cards"],
    },
    "FavoritesView": {
        "area": "Mapa y eventos",
        "where": "Menú → Favoritos",
        "checks": ["Eventos favoritos", "Estado vacío"],
    },
    "MyEventsView": {
        "area": "Mapa y eventos",
        "where": "Menú → Mis eventos",
        "checks": ["Eventos creados por el usuario", "Estados borrador/publicado"],
    },
    "CreateEventView": {
        "area": "Crear / publicar evento",
        "where": "Crear evento (wizard)",
        "checks": ["Flujo completo del wizard", "Pasos y navegación entre steps"],
    },
    "StepEventDetails": {
        "area": "Crear / publicar evento",
        "where": "Crear evento → Detalles",
        "checks": ["Campos título, descripción, categoría", "Validaciones del paso"],
    },
    "StepEventLocation": {
        "area": "Crear / publicar evento",
        "where": "Crear evento → Ubicación",
        "checks": ["Selector de venue/mapa", "Dirección y preview"],
    },
    "StepAgenda": {
        "area": "Crear / publicar evento",
        "where": "Crear evento → Agenda",
        "checks": ["Línea de tiempo / slots", "Agregar/editar ítems"],
    },
    "StepAccessControl": {
        "area": "Crear / publicar evento",
        "where": "Crear evento → Control de acceso",
        "checks": ["Tipos de entrada y permisos", "QR / listas"],
    },
    "StepEventSummary": {
        "area": "Crear / publicar evento",
        "where": "Crear evento → Resumen",
        "checks": ["Resumen antes de publicar", "Botón publicar"],
    },
    "PublishFlowModal": {
        "area": "Crear / publicar evento",
        "where": "Publicar evento",
        "checks": ["Modal de confirmación", "Estados éxito/error"],
    },
    "EventDetailView": {
        "area": "Detalle de evento",
        "where": "Evento → detalle",
        "checks": ["Hero, info, botones comprar/compartir", "Tabs del evento"],
    },
    "EventPreviewModal": {
        "area": "Detalle de evento",
        "where": "Vista previa del evento",
        "checks": ["Preview antes de publicar", "Cierre y acciones"],
    },
    "AccessControlListView": {
        "area": "Control de acceso",
        "where": "Evento → control de acceso",
        "checks": ["Lista de asistentes", "Estados check-in"],
    },
    "ScanQRSheet": {
        "area": "Control de acceso",
        "where": "Evento → escanear QR",
        "checks": ["Scanner QR", "Feedback válido/inválido"],
    },
    "MyInvitationsView": {
        "area": "Invitaciones y tickets",
        "where": "Menú → Mis invitaciones",
        "checks": ["Listado de invitaciones", "Estados pendiente/aceptada"],
    },
    "TicketPurchaseFlow": {
        "area": "Invitaciones y tickets",
        "where": "Comprar ticket",
        "checks": ["Flujo de compra", "Resumen y confirmación"],
    },
    "GuestManagementView": {
        "area": "Invitados",
        "where": "Evento → invitados",
        "checks": ["Lista de invitados", "Acciones invitar/editar"],
    },
    "MessagesListView": {
        "area": "Chat y mensajes",
        "where": "Mensajes → lista",
        "checks": ["Conversaciones", "Badges no leídos"],
    },
    "ChatRoomView": {
        "area": "Chat y mensajes",
        "where": "Chat → sala",
        "checks": ["Burbujas, input, adjuntos", "Scroll y timestamps"],
    },
    "PrivateChatView": {
        "area": "Chat y mensajes",
        "where": "Chat privado",
        "checks": ["DM 1:1", "Header y acciones"],
    },
    "BankingHub": {
        "area": "Pagos y banca",
        "where": "Menú → Pagos / banca",
        "checks": ["Hub de métodos de pago", "Navegación a formularios"],
    },
    "BankingForm": {
        "area": "Pagos y banca",
        "where": "Agregar método de pago",
        "checks": ["Formulario bancario", "Validaciones de campos"],
    },
    "PaymentMethodsDashboard": {
        "area": "Pagos y banca",
        "where": "Métodos de pago",
        "checks": ["Cards de métodos", "Eliminar/editar"],
    },
    "AIAssistantFAB": {
        "area": "Asistente IA",
        "where": "FAB flotante IA",
        "checks": ["Botón flotante visible", "Abre asistente"],
    },
    "AIAssistantView": {
        "area": "Asistente IA",
        "where": "Asistente IA",
        "checks": ["Chat con IA", "Sugerencias y respuestas"],
    },
    "Login": {
        "area": "Autenticación",
        "where": "/login",
        "checks": ["Formulario login", "Google OAuth y links olvidé contraseña"],
    },
    "SignUp": {
        "area": "Autenticación",
        "where": "/signup",
        "checks": ["Registro", "Términos y validaciones"],
    },
    "ForgotPassword": {
        "area": "Autenticación",
        "where": "/forgot-password",
        "checks": ["Recuperar contraseña", "Confirmación envío email"],
    },
    "ResetPassword": {
        "area": "Autenticación",
        "where": "/reset-password",
        "checks": ["Nueva contraseña", "Confirmación"],
    },
    "StoryViewer": {
        "area": "Historias y búsqueda",
        "where": "Feed → historias",
        "checks": ["Visor fullscreen", "Progreso y tap siguiente"],
    },
    "AddStorySheet": {
        "area": "Historias y búsqueda",
        "where": "Crear historia",
        "checks": ["Sheet crear story", "Subir media"],
    },
    "GlobalSearchView": {
        "area": "Historias y búsqueda",
        "where": "Búsqueda global",
        "checks": ["Input búsqueda", "Resultados usuarios/eventos"],
    },
    "AdminPanelView": {
        "area": "Panel admin",
        "where": "Admin → panel",
        "checks": ["Dashboard admin", "Navegación entre paneles"],
    },
    "TopHeader": {
        "area": "Layout / navegación",
        "where": "Header superior",
        "checks": ["Logo, búsqueda, notificaciones, avatar"],
    },
    "SideMenu": {
        "area": "Layout / navegación",
        "where": "Menú lateral",
        "checks": ["Items del menú", "Iconos y rutas"],
    },
    "VenueDetail": {
        "area": "Venues",
        "where": "Detalle de venue",
        "checks": ["Info del venue", "Mapa y eventos asociados"],
    },
}

FOLDER_AREA: dict[str, str] = {
    "auth": "Autenticación",
    "feed": "Feed / Inicio",
    "events": "Mapa y eventos",
    "chat": "Chat y mensajes",
    "banking": "Pagos y banca",
    "access": "Control de acceso",
    "guests": "Invitados",
    "invitations": "Invitaciones y tickets",
    "services": "Servicios",
    "ai": "Asistente IA",
    "admin": "Panel admin",
    "pages": "Autenticación",
    "contexts": "Otros",
    "hooks": "Otros",
}


def component_name(path: str) -> str:
    return Path(path).stem


def _camel_to_label(name: str) -> str:
    overrides = {
        "ProfileView": "Vista Mi perfil",
        "ProfileGallery": "Mi galería",
        "EditProfileView": "Editar perfil",
        "ProfileCommentsView": "Comentarios del perfil",
        "UserProfileView": "Perfil de otro usuario",
        "FeedHero": "Banner del feed",
        "CreatePostSheet": "Crear publicación",
        "AuthLogo": "Logo de autenticación",
        "TermsDialog": "Diálogo de términos",
        "ForgotPassword": "Olvidé mi contraseña",
        "SignUp": "Registro",
        "ResetPassword": "Restablecer contraseña",
        "ChangeLocationSheet": "Cambiar ubicación",
        "FeedBanner": "Banner promocional",
        "GlobalSearchView": "Búsqueda global",
        "StoryViewer": "Visor de historias",
        "AddStorySheet": "Agregar historia",
    }
    if name in overrides:
        return overrides[name]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    for suffix, repl in (("View", ""), ("Sheet", ""), ("Modal", ""), ("Dialog", "")):
        spaced = spaced.replace(suffix, repl)
    return spaced.strip().capitalize()


def hint_for_path(lovable_path: str, status: str, similarity: float) -> dict[str, Any]:
    name = component_name(lovable_path)
    parts = lovable_path.replace("\\", "/").split("/")
    folder = parts[2] if len(parts) > 2 and parts[0] == "src" else "otros"

    meta = COMPONENT_HINTS.get(name, {})
    area = meta.get("area") or FOLDER_AREA.get(folder, "Otros")
    where = meta.get("where") or f"Navegar a «{area}» en la app"
    checks: list[str] = list(meta.get("checks") or [])
    if not checks:
        label = _camel_to_label(name)
        checks = [f"Comparar visualmente «{label}» con diseño Lovable"]

    if status == "missing_in_web":
        action = "Implementar en DoEventsWEB y validar"
    elif status == "needs_adaptation":
        action = "Empalmar diseño Lovable en componente WEB existente"
    elif status == "minor_drift":
        action = "Confirmar ajustes menores de UI"
    else:
        action = "Confirmar que coincide con Lovable"

    return {
        "area": area,
        "feature": _camel_to_label(name),
        "where": where,
        "status": status,
        "statusLabel": STATUS_LABEL.get(status, status),
        "similarityPercent": similarity,
        "action": action,
        "checks": checks,
        "lovablePath": lovable_path,
        "component": name,
    }


def build_validation_checklist(comparison: dict[str, Any], *, include_aligned: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in comparison.get("files") or []:
        status = entry.get("status", "aligned")
        if status == "aligned" and not include_aligned:
            continue
        sim = float(entry.get("similarityPercent", 0))
        if status == "minor_drift" and sim >= 98 and not include_aligned:
            continue
        hint = hint_for_path(entry.get("lovablePath", ""), status, sim)
        items.append(hint)

    priority = {"missing_in_web": 0, "needs_adaptation": 1, "minor_drift": 2, "aligned": 3}

    def sort_key(it: dict[str, Any]) -> tuple:
        area_idx = AREA_ORDER.index(it["area"]) if it["area"] in AREA_ORDER else 99
        return (area_idx, priority.get(it["status"], 9), -it.get("similarityPercent", 0))

    items.sort(key=sort_key)
    return items


def group_by_area(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        grouped.setdefault(it["area"], []).append(it)
    return grouped


def attach_validation_to_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    checklist = build_validation_checklist(comparison)
    for entry in comparison.get("files") or []:
        entry["validationHint"] = hint_for_path(
            entry.get("lovablePath", ""),
            entry.get("status", "aligned"),
            float(entry.get("similarityPercent", 0)),
        )
    comparison["validationChecklist"] = checklist
    comparison["validationChecklistByArea"] = {
        area: len(group) for area, group in group_by_area(checklist).items()
    }
    return comparison
