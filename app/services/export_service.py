"""
Service d'export : génère à la volée un document Markdown ou PDF à partir
des données déjà présentes en base (projet, personnages, épisode).

Aucune donnée supplémentaire n'est stockée : tout est calculé au moment de
la requête, donc ce module n'a strictement aucun coût de base de données.
"""

import os
import io
from datetime import datetime
from urllib.parse import urlparse

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage,
    Table, TableStyle, HRFlowable, KeepTogether
)

# ===== PALETTE (reprend l'identité RBS AIProducer) =====
PURPLE = HexColor("#7e22ce")
PINK = HexColor("#db2777")
DARK = HexColor("#1e1b2e")
MUTED = HexColor("#64748b")
LAVENDER_BG = HexColor("#f5f1fb")
BORDER = HexColor("#e2d9f3")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "assets", "rbs_logo.png")
LOGO_THUMB_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "assets", "rbs_logo_thumb.png")


# ======================================================================
# UTILITAIRES
# ======================================================================

def _resolve_image_path(url: str, static_dir: str):
    """Convertit une URL relative style /static/uploads/xxx.png en chemin
    disque réel. Retourne None (silencieusement) si le fichier n'existe pas,
    pour ne jamais faire planter l'export à cause d'une image manquante."""
    if not url:
        return None
    path = urlparse(url).path
    if path.startswith("/static/"):
        rel = path[len("/static/"):]
    elif path.startswith("static/"):
        rel = path[len("static/"):]
    else:
        rel = path.lstrip("/")
    full_path = os.path.normpath(os.path.join(static_dir, rel))
    return full_path if os.path.isfile(full_path) else None


def _fmt_duration(seconds):
    if not seconds:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    return f"{m}min {s}s" if m else f"{s}s"


def _project_dict(project):
    """Accepte soit un objet SQLAlchemy Project, soit un dict."""
    if isinstance(project, dict):
        return project
    return {
        "title": project.title,
        "idea": project.idea,
        "type": project.type,
        "narrative_style": project.narrative_style,
        "genres": project.genres or [],
        "visual_styles": project.visual_styles or [],
        "duration_seconds": project.duration_seconds,
        "reference_image_world": project.reference_image_world,
        "reference_image_character": project.reference_image_character,
        "extracted_style_prompt": project.extracted_style_prompt,
        "synopsis": project.synopsis,
        "hook": project.hook,
        "status": project.status,
    }


def _char_dict(c):
    if isinstance(c, dict):
        return c
    return {
        "name": c.name, "alias": c.alias, "role": c.role, "age": c.age,
        "traits": c.traits or [], "objective": c.objective,
        "visual_trait": c.visual_trait, "secret": c.secret,
        "arc_potential": c.arc_potential,
        "selected_portrait_url": getattr(c, "selected_portrait_url", None),
    }


def _location_dict(l):
    if isinstance(l, dict):
        return l
    return {
        "name": l.name, "description": l.description, "mood": l.mood,
        "key_visual_details": l.key_visual_details,
        "selected_image_url": getattr(l, "selected_image_url", None),
    }


def _scene_dict(s):
    if isinstance(s, dict):
        return s
    return {
        "number": s.number, "description": s.description, "camera_movement": s.camera_movement,
        "mood": s.mood, "dialogue": s.dialogue, "duration_seconds": s.duration_seconds,
        "is_cliffhanger": s.is_cliffhanger, "episode_title": getattr(s, "episode_title", ""),
        "character_names": getattr(s, "character_names", []), "location_name": getattr(s, "location_name", None),
        "selected_storyboard_url": getattr(s, "selected_storyboard_url", None),
    }


def _episode_dict(e):
    if isinstance(e, dict):
        return e
    return {
        "title": e.title, "script_content": e.script_content,
        "episode_number": getattr(e, "episode_number", None),
        "ends_with_cliffhanger": getattr(e, "ends_with_cliffhanger", False),
    }


# ======================================================================
# MARKDOWN
# ======================================================================

def build_markdown(project, characters, episodes, section: str = "all", base_url: str = "",
                    locations=None, scenes=None) -> str:
    p = _project_dict(project)
    chars = [_char_dict(c) for c in characters]
    eps = [_episode_dict(e) for e in episodes]
    locs = [_location_dict(l) for l in (locations or [])]
    shots = [_scene_dict(s) for s in (scenes or [])]

    lines = []
    lines.append(f"# {p.get('title', 'Untitled Project')}")
    lines.append("")
    lines.append("*RBS AIProducer — Cinematic AI Studio*")
    lines.append(f"*Exported on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    lines.append("---")

    if section in ("all",):
        lines.append("")
        lines.append("## Project Settings")
        lines.append("")
        lines.append(f"- **Idea:** {p.get('idea') or 'N/A'}")
        lines.append(f"- **Type:** {p.get('type') or 'N/A'}")
        lines.append(f"- **Duration:** {_fmt_duration(p.get('duration_seconds'))}")
        lines.append(f"- **Narrative Style:** {p.get('narrative_style') or 'N/A'}")
        lines.append(f"- **Genres:** {', '.join(p.get('genres') or []) or 'N/A'}")
        lines.append(f"- **Visual Styles:** {', '.join(p.get('visual_styles') or []) or 'N/A'}")
        if p.get("extracted_style_prompt"):
            lines.append(f"- **Style Prompt:** {p['extracted_style_prompt']}")
        lines.append("")

        world_img = p.get("reference_image_world")
        char_img = p.get("reference_image_character")
        if world_img or char_img:
            lines.append("### Reference Images")
            lines.append("")
            if world_img:
                lines.append(f"**World Style**  ")
                lines.append(f"![World Style]({base_url}{world_img})")
                lines.append("")
            if char_img:
                lines.append(f"**Character Style**  ")
                lines.append(f"![Character Style]({base_url}{char_img})")
                lines.append("")

    if section in ("all", "synopsis"):
        lines.append("## Synopsis & Hook")
        lines.append("")
        lines.append(f"> **Hook:** {p.get('hook') or 'N/A'}")
        lines.append("")
        lines.append(p.get("synopsis") or "*No synopsis generated yet.*")
        lines.append("")

    if section in ("all", "casting"):
        lines.append(f"## Characters ({len(chars)})")
        lines.append("")
        for c in chars:
            title = c.get("name", "Unknown")
            if c.get("alias"):
                title += f' "{c["alias"]}"'
            title += f" — {c.get('role', '')}"
            if c.get("age"):
                title += f" ({c['age']})"
            lines.append(f"### {title}")
            if c.get("selected_portrait_url"):
                lines.append(f"![{c.get('name')}]({base_url}{c['selected_portrait_url']})")
                lines.append("")
            if c.get("visual_trait"):
                lines.append(f"- **Visual:** {c['visual_trait']}")
            if c.get("objective"):
                lines.append(f"- **Objective:** {c['objective']}")
            if c.get("secret"):
                lines.append(f"- **Secret:** {c['secret']}")
            if c.get("traits"):
                lines.append(f"- **Traits:** {', '.join(c['traits'])}")
            if c.get("arc_potential"):
                lines.append(f"- **Arc Potential:** {c['arc_potential']}")
            lines.append("")

    if section in ("all", "script"):
        for i, ep in enumerate(eps):
            ep_num = ep.get("episode_number") or (i + 1)
            label = f"Episode {ep_num}" if len(eps) > 1 else "Script"
            lines.append(f"## {label} — {ep.get('title', 'Untitled')}")
            lines.append("")
            lines.append("```")
            lines.append(ep.get("script_content") or "")
            lines.append("```")
            lines.append("")

    if section == "images":
        lines.append(f"## Character Images ({len(chars)})")
        lines.append("")
        for c in chars:
            lines.append(f"### {c.get('name', 'Unknown')}")
            if c.get("selected_portrait_url"):
                lines.append(f"![{c.get('name')}]({base_url}{c['selected_portrait_url']})")
            else:
                lines.append("*No portrait selected yet.*")
            lines.append("")

    if section == "locations":
        lines.append(f"## Locations ({len(locs)})")
        lines.append("")
        for l in locs:
            lines.append(f"### {l.get('name', 'Unknown')}")
            if l.get("selected_image_url"):
                lines.append(f"![{l.get('name')}]({base_url}{l['selected_image_url']})")
                lines.append("")
            if l.get("description"):
                lines.append(f"- **Description:** {l['description']}")
            if l.get("mood"):
                lines.append(f"- **Mood:** {l['mood']}")
            if l.get("key_visual_details"):
                lines.append(f"- **Key Visual Details:** {l['key_visual_details']}")
            lines.append("")

    if section == "storyboard":
        lines.append(f"## Storyboard ({len(shots)} shot(s))")
        lines.append("")
        current_ep = None
        for s in shots:
            if s.get("episode_title") != current_ep:
                current_ep = s.get("episode_title")
                lines.append(f"### {current_ep}")
                lines.append("")
            title = f"Shot {s.get('number')}" + (" — Cliffhanger" if s.get("is_cliffhanger") else "")
            lines.append(f"**{title}**  ")
            if s.get("selected_storyboard_url"):
                lines.append(f"![{title}]({base_url}{s['selected_storyboard_url']})")
                lines.append("")
            lines.append(f"- **Description:** {s.get('description') or 'N/A'}")
            if s.get("camera_movement"):
                lines.append(f"- **Camera:** {s['camera_movement']}")
            if s.get("dialogue"):
                lines.append(f"- **Dialogue:** {s['dialogue']}")
            lines.append(f"- **Duration:** {s.get('duration_seconds')}s")
            if s.get("character_names"):
                lines.append(f"- **Characters:** {', '.join(s['character_names'])}")
            if s.get("location_name"):
                lines.append(f"- **Location:** {s['location_name']}")
            lines.append("")

    return "\n".join(lines)


# ======================================================================
# PDF
# ======================================================================

def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle("cover_title", parent=base["Title"], fontSize=26,
                                       textColor=DARK, alignment=TA_CENTER, spaceBefore=18, spaceAfter=6),
        "cover_tagline": ParagraphStyle("cover_tagline", parent=base["Normal"], fontSize=11,
                                         textColor=PURPLE, alignment=TA_CENTER, spaceAfter=4,
                                         fontName="Helvetica-Oblique"),
        "cover_meta": ParagraphStyle("cover_meta", parent=base["Normal"], fontSize=9,
                                      textColor=MUTED, alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=16, textColor=PURPLE,
                              spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold"),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, textColor=DARK,
                              spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10, leading=15,
                                textColor=DARK, spaceAfter=6),
        "hook": ParagraphStyle("hook", parent=base["Normal"], fontSize=11.5, leading=16,
                                textColor=PINK, fontName="Helvetica-Oblique", spaceAfter=10),
        "meta_label": ParagraphStyle("meta_label", parent=base["Normal"], fontSize=8.5,
                                      textColor=MUTED, fontName="Helvetica-Bold"),
        "meta_value": ParagraphStyle("meta_value", parent=base["Normal"], fontSize=9.5,
                                      textColor=DARK, spaceAfter=4),
        "script": ParagraphStyle("script", parent=base["Normal"], fontSize=9.5, leading=14,
                                  textColor=DARK, fontName="Courier", spaceAfter=4),
        "img_caption": ParagraphStyle("img_caption", parent=base["Normal"], fontSize=8,
                                       textColor=MUTED, alignment=TA_CENTER, spaceBefore=2),
    }


def _decorate_page(canvas, doc):
    """Bande de couleur + logo + pied de page, dessinés sur chaque page."""
    canvas.saveState()
    width, height = A4

    # Bande fine en haut
    canvas.setFillColor(PURPLE)
    canvas.rect(0, height - 4, width, 4, fill=1, stroke=0)

    # Logo miniature en haut à droite (si dispo)
    if os.path.isfile(LOGO_THUMB_PATH):
        try:
            canvas.drawImage(LOGO_THUMB_PATH, width - 25 * mm, height - 22 * mm,
                              width=14 * mm, height=14 * mm, mask="auto",
                              preserveAspectRatio=True)
        except Exception:
            pass

    # Pied de page
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm, "RBS AIProducer — Cinematic AI Studio")
    canvas.drawRightString(width - 20 * mm, 10 * mm, f"Page {doc.page}")

    canvas.restoreState()


def _character_table(c, styles, static_dir=""):
    """Une fiche personnage sous forme de mini-tableau à fond clair, avec
    portrait sélectionné si disponible."""
    title = c.get("name", "Unknown")
    if c.get("alias"):
        title += f' "{c["alias"]}"'
    subtitle = c.get("role", "")
    if c.get("age"):
        subtitle += f" · {c['age']} y/o"

    text_rows = [[Paragraph(f"<b>{title}</b> — {subtitle}", styles["h2"])]]
    for label, key in [("Visual", "visual_trait"), ("Objective", "objective"),
                        ("Secret", "secret"), ("Arc Potential", "arc_potential")]:
        if c.get(key):
            text_rows.append([Paragraph(f"<b>{label}:</b> {c[key]}", styles["body"])])
    if c.get("traits"):
        text_rows.append([Paragraph(f"<b>Traits:</b> {', '.join(c['traits'])}", styles["body"])])

    text_table = Table(text_rows, colWidths=[160 * mm])
    text_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LAVENDER_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    portrait_path = _resolve_image_path(c.get("selected_portrait_url"), static_dir) if static_dir else None
    if not portrait_path:
        return text_table

    try:
        img = RLImage(portrait_path, width=35 * mm, height=35 * mm)
    except Exception:
        return text_table

    wrapper = Table([[img, text_table]], colWidths=[38 * mm, 122 * mm])
    wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def _location_card(l, styles, static_dir=""):
    """Fiche décor : même esprit visuel que _character_table."""
    rows = [[Paragraph(f"<b>{l.get('name', 'Unknown')}</b>", styles["h2"])]]
    for label, key in [("Description", "description"), ("Mood", "mood"), ("Key Visual Details", "key_visual_details")]:
        if l.get(key):
            rows.append([Paragraph(f"<b>{label}:</b> {l[key]}", styles["body"])])

    text_table = Table(rows, colWidths=[160 * mm])
    text_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LAVENDER_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    img_path = _resolve_image_path(l.get("selected_image_url"), static_dir) if static_dir else None
    if not img_path:
        return text_table
    try:
        img = RLImage(img_path, width=45 * mm, height=30 * mm)
    except Exception:
        return text_table

    wrapper = Table([[img, text_table]], colWidths=[48 * mm, 112 * mm])
    wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def _scene_card(s, styles, static_dir=""):
    """Fiche plan/storyboard."""
    title = f"Shot {s.get('number')}" + (" — Cliffhanger" if s.get("is_cliffhanger") else "")
    rows = [[Paragraph(f"<b>{title}</b>", styles["h2"])]]
    rows.append([Paragraph(f"<b>Description:</b> {s.get('description') or 'N/A'}", styles["body"])])
    if s.get("camera_movement"):
        rows.append([Paragraph(f"<b>Camera:</b> {s['camera_movement']}", styles["body"])])
    if s.get("dialogue"):
        rows.append([Paragraph(f"<b>Dialogue:</b> {s['dialogue']}", styles["body"])])
    meta_bits = [f"Duration: {s.get('duration_seconds')}s"]
    if s.get("character_names"):
        meta_bits.append(f"Characters: {', '.join(s['character_names'])}")
    if s.get("location_name"):
        meta_bits.append(f"Location: {s['location_name']}")
    rows.append([Paragraph(" · ".join(meta_bits), styles["body"])])

    text_table = Table(rows, colWidths=[160 * mm])
    text_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LAVENDER_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    img_path = _resolve_image_path(s.get("selected_storyboard_url"), static_dir) if static_dir else None
    if not img_path:
        return text_table
    try:
        img = RLImage(img_path, width=45 * mm, height=25 * mm)
    except Exception:
        return text_table

    wrapper = Table([[img, text_table]], colWidths=[48 * mm, 112 * mm])
    wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def _script_flowables(script_content, styles):
    """Formate le script en respectant [ACTION] (italique) et lignes de
    dialogue (gras si tout en majuscules, cas typique NOM: ...)."""
    flowables = []
    for raw_line in (script_content or "").split("\n"):
        line = raw_line.strip()
        if not line:
            flowables.append(Spacer(1, 4))
            continue
        safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        if safe.startswith("[") and "]" in safe:
            flowables.append(Paragraph(f"<i>{safe}</i>", styles["script"]))
        elif safe.isupper() or (":" in safe and safe.split(":")[0].isupper()):
            flowables.append(Paragraph(f"<b>{safe}</b>", styles["script"]))
        else:
            flowables.append(Paragraph(safe, styles["script"]))
    return flowables


def build_pdf(project, characters, episodes, section: str = "all", static_dir: str = "",
              locations=None, scenes=None) -> bytes:
    p = _project_dict(project)
    chars = [_char_dict(c) for c in characters]
    eps = [_episode_dict(e) for e in episodes]
    locs = [_location_dict(l) for l in (locations or [])]
    shots = [_scene_dict(s) for s in (scenes or [])]
    styles = _styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=22 * mm, bottomMargin=18 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
        title=p.get("title", "Project"), author="RBS AIProducer"
    )

    story = []

    # ---------- COUVERTURE ----------
    if os.path.isfile(LOGO_PATH):
        try:
            story.append(Spacer(1, 30 * mm))
            story.append(RLImage(LOGO_PATH, width=38 * mm, height=38 * mm))
        except Exception:
            story.append(Spacer(1, 45 * mm))
    else:
        story.append(Spacer(1, 45 * mm))

    story.append(Spacer(1, 8))
    story.append(Paragraph(p.get("title", "Untitled Project"), styles["cover_title"]))
    if p.get("hook"):
        story.append(Paragraph(f"“{p['hook']}”", styles["cover_tagline"]))
    section_label = {"all": "Full Production Bible", "synopsis": "Synopsis & Hook",
                      "casting": "Character Casting", "script": "Script",
                      "images": "Character Images", "locations": "Locations",
                      "storyboard": "Storyboard"}.get(section, "Export")
    story.append(Spacer(1, 10))
    story.append(Paragraph(section_label, styles["cover_meta"]))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["cover_meta"]))
    story.append(PageBreak())

    # ---------- PROJECT SETTINGS + IMAGES DE RÉFÉRENCE ----------
    if section == "all":
        story.append(Paragraph("Project Settings", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=8))

        meta_rows = [
            ["Idea", p.get("idea") or "N/A"],
            ["Type", p.get("type") or "N/A"],
            ["Duration", _fmt_duration(p.get("duration_seconds"))],
            ["Narrative Style", p.get("narrative_style") or "N/A"],
            ["Genres", ", ".join(p.get("genres") or []) or "N/A"],
            ["Visual Styles", ", ".join(p.get("visual_styles") or []) or "N/A"],
        ]
        table_data = [[Paragraph(f"<b>{k}</b>", styles["meta_label"]), Paragraph(v, styles["meta_value"])]
                       for k, v in meta_rows]
        meta_table = Table(table_data, colWidths=[35 * mm, 125 * mm])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        world_path = _resolve_image_path(p.get("reference_image_world"), static_dir)
        char_path = _resolve_image_path(p.get("reference_image_character"), static_dir)
        if world_path or char_path:
            story.append(Paragraph("Reference Images", styles["h2"]))
            img_cells, caption_cells = [], []
            for path, caption in [(world_path, "World Style"), (char_path, "Character Style")]:
                if path:
                    try:
                        img_cells.append(RLImage(path, width=60 * mm, height=60 * mm))
                        caption_cells.append(Paragraph(caption, styles["img_caption"]))
                    except Exception:
                        pass
            if img_cells:
                img_table = Table([img_cells, caption_cells], colWidths=[65 * mm] * len(img_cells))
                img_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(img_table)
        story.append(Spacer(1, 6))
        story.append(PageBreak())

    # ---------- SYNOPSIS & HOOK ----------
    if section in ("all", "synopsis"):
        story.append(Paragraph("Synopsis & Hook", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=8))
        if p.get("hook"):
            story.append(Paragraph(f"“{p['hook']}”", styles["hook"]))
        story.append(Paragraph(p.get("synopsis") or "No synopsis generated yet.", styles["body"]))
        if section == "all":
            story.append(PageBreak())

    # ---------- CASTING ----------
    if section in ("all", "casting"):
        story.append(Paragraph(f"Characters ({len(chars)})", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=10))
        for c in chars:
            story.append(KeepTogether([_character_table(c, styles, static_dir), Spacer(1, 8)]))
        if section == "all":
            story.append(PageBreak())

    # ---------- SCRIPT ----------
    if section in ("all", "script"):
        for i, ep in enumerate(eps):
            ep_num = ep.get("episode_number") or (i + 1)
            label = f"Episode {ep_num}" if len(eps) > 1 else "Script"
            if i > 0:
                story.append(PageBreak())
            story.append(Paragraph(f"{label} — {ep.get('title', 'Untitled')}", styles["h1"]))
            story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=8))
            story.extend(_script_flowables(ep.get("script_content", ""), styles))
            story.append(Spacer(1, 10))

    # ---------- CHARACTER IMAGES (portrait sélectionné, en grand) ----------
    if section == "images":
        story.append(Paragraph(f"Character Images ({len(chars)})", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=10))
        for c in chars:
            img_path = _resolve_image_path(c.get("selected_portrait_url"), static_dir)
            story.append(Paragraph(c.get("name", "Unknown"), styles["h2"]))
            if img_path:
                try:
                    story.append(RLImage(img_path, width=70 * mm, height=70 * mm))
                except Exception:
                    story.append(Paragraph("Image could not be loaded.", styles["body"]))
            else:
                story.append(Paragraph("No portrait selected yet.", styles["body"]))
            story.append(Spacer(1, 10))

    # ---------- LOCATIONS ----------
    if section == "locations":
        story.append(Paragraph(f"Locations ({len(locs)})", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=10))
        for l in locs:
            story.append(KeepTogether([_location_card(l, styles, static_dir), Spacer(1, 8)]))

    # ---------- STORYBOARD ----------
    if section == "storyboard":
        story.append(Paragraph(f"Storyboard ({len(shots)} shot(s))", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER, spaceAfter=10))
        current_ep = None
        for s in shots:
            if s.get("episode_title") != current_ep:
                current_ep = s.get("episode_title")
                story.append(Paragraph(current_ep or "Episode", styles["h2"]))
            story.append(KeepTogether([_scene_card(s, styles, static_dir), Spacer(1, 6)]))

    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    buffer.seek(0)
    return buffer.read()
