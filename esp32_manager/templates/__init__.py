from typing import Dict, List
import logging


from esp32_manager.templates.base import BaseTemplate
from esp32_manager.templates.basic import BasicTemplate
from esp32_manager.templates.iot import IoTTemplate
# from esp32_manager.templates.sensor import SensorTemplate
# from esp32_manager.templates.webserver import WebServerTemplate

logger = logging.getLogger(__name__)

TEMPLATES = {
    'basic': BasicTemplate,
    'iot': IoTTemplate,
    # 'sensor': SensorTemplate,
    # 'webserver': WebServerTemplate,
}

def get_available_templates() -> List[str]:
    """Get list of available template names."""
    return list(TEMPLATES.keys())

def get_template_info(template_name: str) -> Dict[str, str]:
    """Get template information."""
    if template_name not in TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found.")

    template_class = TEMPLATES[template_name]
    return {
        'name': template_name,
        'description': template_class.description,
        'author': getattr(template_class, 'author', 'ESP32Manager'),
        'version': getattr(template_class, 'version', '1.0.0'),
        'dependencies': getattr(template_class, 'dependencies', []),
        'features': getattr(template_class, 'features', []),
    }

def get_template_files(template_name: str, config) -> Dict[str, str]:
    """Get template files for project creation."""
    if template_name not in TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found.")

    template_class = TEMPLATES[template_name]
    template_instance = template_class(config)

    try:
        files = template_instance.generate_files()
        logger.info(f"Generated {len(files)} files for template '{template_name}'")
        return files
    except Exception as e:
        logger.error(f"Failed to generate {template_name} files: {e}")
        raise

def validate_template(template_name: str) -> bool:
    """Validate that a template exists and is properly configured."""
    if template_name not in TEMPLATES:
        raise False

    template_class = TEMPLATES[template_name]

    # Check required attributes
    required_attrs = ['description', 'generate_files']
    for attr in required_attrs:
        if not hasattr(template_class, attr):
            logger.warning(f" Template '{template_name}' missing required attribute '{attr}'")
            return False

    return True

