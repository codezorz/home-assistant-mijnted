from typing import Optional
from homeassistant.core import HomeAssistant


class TranslationUtil:
    """Utility class for translations."""
    
    @staticmethod
    def translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
        """Translate room codes to full room names using Home Assistant's translation system.
        
        Args:
            room_code: Room code to translate (e.g., "KA", "W")
            hass: Home Assistant instance for translations (optional)
            
        Returns:
            Translated room name or original code if translation not found
        """
        if hass:
            try:
                from ..const import DOMAIN
                
                language = hass.config.language or "en"
                
                translations_data = hass.data.get("frontend_translations", {})
                if language in translations_data:
                    translations = translations_data[language]
                    
                    translation_keys = [
                        f"component.{DOMAIN}.entity.sensor.room_codes.{room_code}",
                        f"component.{DOMAIN}.room_codes.{room_code}",
                        f"room_codes.{room_code}"
                    ]
                    
                    for key in translation_keys:
                        if key in translations:
                            translated = translations[key]
                            if translated and translated != key:
                                return translated
                    
                    if "room_codes" in translations:
                        room_translations = translations.get("room_codes", {})
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
                
                entity_translations = hass.data.get("entity_translations", {})
                if language in entity_translations:
                    domain_translations = entity_translations[language].get(DOMAIN, {})
                    if "room_codes" in domain_translations:
                        room_translations = domain_translations["room_codes"]
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
            except Exception:
                pass
        
        room_translations = {
            "KA": "bedroom",
            "W": "living room"
        }
        return room_translations.get(room_code, room_code)

