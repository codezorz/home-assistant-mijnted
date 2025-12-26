from typing import Optional
from homeassistant.core import HomeAssistant


class TranslationUtil:
    """Utility class for translations."""
    
    @staticmethod
    async def async_translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
        """Translate room codes to full room names using Home Assistant's translation system.
        
        Args:
            room_code: Room code to translate (e.g., "KA", "W")
            hass: Home Assistant instance for translations (optional)
            
        Returns:
            Translated room name or original code if translation not found
        """
        if hass:
            try:
                # Use Home Assistant's translation system
                from homeassistant.helpers import translation
                
                # Get the current language
                language = hass.config.language or "en"
                
                # Load translations for the integration
                # Use the domain name for translation loading
                from ..const import DOMAIN
                translations = await translation.async_get_translations(
                    hass, "entity", language, [DOMAIN]
                )
                
                # Try to get translation from integration translation files
                # Format: "component.mijnted.room_codes.KA" or similar
                translation_key = f"room_codes.{room_code}"
                if translation_key in translations:
                    translated = translations[translation_key]
                    if translated and translated != translation_key:
                        return translated
                
                # Also try direct access to room_codes in translations
                if "room_codes" in translations:
                    room_translations = translations.get("room_codes", {})
                    if isinstance(room_translations, dict) and room_code in room_translations:
                        return room_translations[room_code]
            except Exception:
                # Fall through to fallback translations
                pass
        
        # Fallback to hardcoded translations
        room_translations = {
            "KA": "bedroom",
            "W": "living room",
        }
        return room_translations.get(room_code, room_code)
    
    @staticmethod
    def translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
        """Translate room codes to full room names using Home Assistant's translation system.
        
        This is a synchronous version that uses already-loaded translations from hass.data.
        For async contexts where translations may need to be loaded, use async_translate_room_code().
        
        Args:
            room_code: Room code to translate (e.g., "KA", "W")
            hass: Home Assistant instance for translations (optional)
            
        Returns:
            Translated room name or original code if translation not found
        """
        if hass:
            try:
                from ..const import DOMAIN
                
                # Get the current language
                language = hass.config.language or "en"
                
                # Try to get translations from already-loaded translation data
                # Check frontend_translations first (most common)
                translations_data = hass.data.get("frontend_translations", {})
                if language in translations_data:
                    translations = translations_data[language]
                    
                    # Try various translation key formats
                    translation_keys = [
                        f"component.{DOMAIN}.entity.sensor.room_codes.{room_code}",
                        f"component.{DOMAIN}.room_codes.{room_code}",
                        f"room_codes.{room_code}",
                    ]
                    
                    for key in translation_keys:
                        if key in translations:
                            translated = translations[key]
                            if translated and translated != key:
                                return translated
                    
                    # Also try direct access to room_codes
                    if "room_codes" in translations:
                        room_translations = translations.get("room_codes", {})
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
                
                # Try entity_translations
                entity_translations = hass.data.get("entity_translations", {})
                if language in entity_translations:
                    domain_translations = entity_translations[language].get(DOMAIN, {})
                    if "room_codes" in domain_translations:
                        room_translations = domain_translations["room_codes"]
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
            except Exception:
                # Fall through to fallback translations
                pass
        
        # Fallback to hardcoded translations
        room_translations = {
            "KA": "bedroom",
            "W": "living room",
        }
        return room_translations.get(room_code, room_code)

