from app.schemas.dates import EventDateModel
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PaletteKey = Literal["background", "text", "heading", "hero_text", "details_background", "memory_background", "memory_text", "badge_background", "badge_text", "button_background", "button_text", "countdown_background", "countdown_text"]
Palette = dict[PaletteKey, Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]]

class InvitationPresentation(BaseModel):
    editor_saved: bool = False
    appearance_confirmed: bool = False
    colors_confirmed: bool = False
    opening_hand: Literal["gloved", "witch"] = "gloved"
    button_radius: int | None = Field(default=None, ge=0, le=999)
    opening_background_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("opening_background_color", mode="before")
    @classmethod
    def empty_opening_background_to_none(cls, value):
        return None if value == "" else value

    paper_style: Literal["none", "straight", "arch", "wave", "deckle", "ticket"] = "none"
    paper_texture: Literal["cotton", "floral"] = "cotton"
    paper_color: str = Field(default="#F5F0E6", pattern=r"^#[0-9a-fA-F]{6}$")
    paper_text: str = Field(default="#354634", pattern=r"^#[0-9a-fA-F]{6}$")
    paper_target: Literal["hero", "details", "all"] = "details"
    photo_layout: Literal["hidden", "stacked", "grid", "asymmetric"] = "stacked"
    photo_columns: Literal[2, 3, 4] = 2
    section_transition: Literal["none", "torn", "wave"] = "none"
    transition_target: Literal["all", "hero", "story", "details", "memories", "exhibition"] = "all"
    transition_color: str = Field(default="#F5F0E6", pattern=r"^#[0-9a-fA-F]{6}$")

class VisualLayer(BaseModel):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    position: Literal["sticker-story", "sticker-details", "sticker-memories", "sticker-exhibition", "sticker-countdown", "invitation-background", "opening-background", "story-background", "details-background", "memories-background", "exhibition-background", "countdown-background", "footer-background", "hero-background", "hero-foreground", "after-hero", "after-story", "after-details", "before-memories"] = "after-hero"
    background_fit: Literal["cover", "contain", "repeat"] = "cover"
    placement: Literal["custom", "top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"] = "custom"
    frame: Literal["none", "arch", "oval", "polaroid", "gold", "baroque"] = "none"
    motion: Literal["none", "grow", "shrink", "sway", "parallax", "slide-right", "slide-left", "across-right", "across-left", "unfold-right", "unfold-left", "spin", "spin-away", "fade-away"] = "none"
    width: int = Field(default=70, ge=5, le=100)
    x: int = Field(default=50, ge=0, le=100)
    y: int = Field(default=75, ge=0, le=100)
    caption: str = Field(default="", max_length=255)

class VisualLayerPublic(VisualLayer):
    src: str


class InvitationPublic(EventDateModel):
    model_config = ConfigDict(from_attributes=True)
    presentation: InvitationPresentation = Field(default_factory=InvitationPresentation)
    visual_layers: list[VisualLayerPublic] = Field(default_factory=list)

    palette: Palette = Field(default_factory=dict)
    envelope_color: str = Field(default="#25463B", pattern=r"^#[0-9a-fA-F]{6}$")
    ribbon_color: str = Field(default="#718CA2", pattern=r"^#[0-9a-fA-F]{6}$")
    seal_color: str = Field(default="#C9AA78", pattern=r"^#[0-9a-fA-F]{6}$")
    paper_color: str = Field(default="#fffdf7", pattern=r"^#[0-9a-fA-F]{6}$")
    envelope_texture: Literal["smooth", "linen", "grain"] = "linen"
    envelope_pattern: Literal["plain", "pinstripe", "botanical", "lace", "floral_cut", "embossed"] = "plain"
    seal_motif: Literal["original", "botanical", "heart", "monogram"] = "original"
    address: str = Field(default="", max_length=1000)
    transport_notes: str = Field(default="", max_length=2000)
    contact_info: str = Field(default="", max_length=1000)
    schedule: str = Field(default="", max_length=3000)
    opening_style: Literal["classic", "envelope"] = "classic"
    name: str
    slug: str
    event_date: datetime | None = None
    venue: str = ""
    city: str = ""
    tagline: str = ""
    story_title: str = ""
    story_text: str = ""
    guest_note: str = ""
    signature_text: str = ""
    memory_title: str = ""
    memory_text: str = ""
    language: Literal["tr", "en"] = "tr"
    design_theme: Literal["romantic", "minimal", "celebration"] = "romantic"
    memory_cover_url: str | None = None
    cover_url: str | None = None
    music_url: str | None = None
    music_filename: str | None = None


class InvitationUpdateAdmin(EventDateModel):
    presentation: InvitationPresentation = Field(default_factory=InvitationPresentation)
    visual_layers: list[VisualLayer] = Field(default_factory=list, max_length=32)
    palette: Palette = Field(default_factory=dict)
    envelope_color: str = Field(default="#25463B", pattern=r"^#[0-9a-fA-F]{6}$")
    ribbon_color: str = Field(default="#718CA2", pattern=r"^#[0-9a-fA-F]{6}$")
    seal_color: str = Field(default="#C9AA78", pattern=r"^#[0-9a-fA-F]{6}$")
    paper_color: str = Field(default="#fffdf7", pattern=r"^#[0-9a-fA-F]{6}$")
    envelope_texture: Literal["smooth", "linen", "grain"] = "linen"
    envelope_pattern: Literal["plain", "pinstripe", "botanical", "lace", "floral_cut", "embossed"] = "plain"
    seal_motif: Literal["original", "botanical", "heart", "monogram"] = "original"
    address: str = Field(default="", max_length=1000)
    transport_notes: str = Field(default="", max_length=2000)
    contact_info: str = Field(default="", max_length=1000)
    schedule: str = Field(default="", max_length=3000)
    opening_style: Literal["classic", "envelope"] = "classic"
    name: str | None = Field(default=None, max_length=255)
    event_date: datetime | None = None
    venue: str | None = None
    city: str | None = None
    tagline: str | None = None
    story_title: str | None = None
    story_text: str | None = None
    guest_note: str | None = None
    signature_text: str = Field(default="", max_length=255)
    memory_title: str = Field(default="", max_length=255)
    memory_text: str = Field(default="", max_length=2000)
    language: Literal["tr", "en"] = "tr"
    design_theme: Literal["romantic", "minimal", "celebration"] = "romantic"

    @field_validator("name", mode="before")
    @classmethod
    def empty_name_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value
