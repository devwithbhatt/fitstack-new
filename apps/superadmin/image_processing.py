import io
import logging
import os
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

# Get the root logger to ensure the message is captured.
logger = logging.getLogger()

def process_image(image_field):
    """
    Makes image WhatsApp compliant:
    - Fixes EXIF rotation
    - Converts to RGB
    - Resizes to max 800x800
    - Saves as optimized JPEG
    """
    # This print statement will absolutely appear in your server's console logs if this code runs.
    print("!!! RUNNING PROCESS_IMAGE FUNCTION !!!")
    logger.warning("!!! LOGGER: RUNNING PROCESS_IMAGE FUNCTION !!!")

    if not image_field:
        logger.warning("Image field is empty, skipping processing.")
        return

    try:
        logger.warning(f"Starting image processing for {image_field.name}")
        img = Image.open(image_field)

        # Fix rotation from mobile uploads
        img = ImageOps.exif_transpose(img)
        logger.warning("Image orientation corrected.")

        # Convert to RGB (removes CMYK / transparency issues)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            logger.warning("Image converted to RGB.")

        # Resize safely
        img.thumbnail((800, 800))
        logger.warning(f"Image resized to {img.size}.")

        # Save to memory buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=80, optimize=True)
        buffer.seek(0)
        logger.warning("Image saved to buffer as JPEG.")

        # Get the base name and create a new .jpg name
        base_name, _ = os.path.splitext(image_field.name)
        file_name = f"{base_name}.jpg"

        # Properly update Django FileField
        image_field.save(file_name, ContentFile(buffer.read()), save=False)
        logger.warning(f"Image processing successful. New file name: {file_name}")
        print(f"!!! SUCCESS: Image processing successful for {file_name} !!!")

    except Exception as e:
        # If anything goes wrong, log the full error in the most visible way possible.
        print(f"!!!!!!!!!! CRITICAL IMAGE PROCESSING ERROR !!!!!!!!!!")
        print(f"Error processing {image_field.name}. Error: {e}")
        logger.critical(f"CRITICAL: Image processing failed for {image_field.name}. Error: {e}", exc_info=True)