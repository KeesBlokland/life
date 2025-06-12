"""
/home/life/app/utils/util_image.py
Version: 1.0.0
Purpose: Image processing - HEIC conversion, resizing, thumbnails
Created: 2025-06-11
"""

import os
from PIL import Image
from flask import current_app

# Try to import HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

def process_image_file(filepath):
    """
    Process image file - convert HEIC to JPG, resize if needed
    Returns: path to processed file
    """
    try:
        # Check if file is HEIC
        if filepath.lower().endswith('.heic'):
            if not HEIC_SUPPORT:
                if current_app:
                    current_app.logger.error("HEIC file uploaded but pillow-heif not installed")
                return filepath
            
            # Convert HEIC to JPG
            new_filepath = convert_heic_to_jpg(filepath)
            if new_filepath != filepath:
                # Remove original HEIC file
                os.remove(filepath)
                filepath = new_filepath
        
        # Resize if needed
        filepath = resize_image_if_needed(filepath)
        
        # Generate thumbnail
        generate_thumbnail(filepath)
        
        return filepath
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error processing image {filepath}: {str(e)}")
        return filepath

def convert_heic_to_jpg(heic_path):
    """Convert HEIC file to JPG"""
    try:
        # Open HEIC file
        img = Image.open(heic_path)
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Create new filename
        jpg_path = heic_path.rsplit('.', 1)[0] + '.jpg'
        
        # Save as JPG
        img.save(jpg_path, 'JPEG', quality=current_app.config.get('IMAGE_QUALITY', 85))
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Converted HEIC to JPG: {heic_path} -> {jpg_path}")
        
        return jpg_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to convert HEIC: {str(e)}")
        return heic_path

def resize_image_if_needed(image_path):
    """Resize image if larger than configured max size"""
    try:
        max_size = current_app.config.get('IMAGE_MAX_SIZE', 1024)
        
        # Open image
        img = Image.open(image_path)
        
        # Check if resize needed
        if max(img.size) <= max_size:
            return image_path
        
        # Calculate new size maintaining aspect ratio
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Save resized image
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            img.save(image_path, 'JPEG', quality=current_app.config.get('IMAGE_QUALITY', 85))
        elif image_path.lower().endswith('.png'):
            img.save(image_path, 'PNG', optimize=True)
        else:
            img.save(image_path)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Resized image: {image_path} to max dimension {max_size}px")
        
        return image_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to resize image: {str(e)}")
        return image_path

def generate_thumbnail(image_path):
    """Generate thumbnail for image"""
    try:
        # Create thumbnail directory
        thumb_dir = os.path.join(os.path.dirname(image_path), '.thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)
        
        # Thumbnail path
        filename = os.path.basename(image_path)
        thumb_path = os.path.join(thumb_dir, f"thumb_{filename}")
        
        # Skip if thumbnail exists
        if os.path.exists(thumb_path):
            return thumb_path
        
        # Open and create thumbnail
        img = Image.open(image_path)
        img.thumbnail((200, 200), Image.Resampling.LANCZOS)
        
        # Save thumbnail
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            img.save(thumb_path, 'JPEG', quality=70)
        elif image_path.lower().endswith('.png'):
            img.save(thumb_path, 'PNG', optimize=True)
        else:
            img.save(thumb_path)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Generated thumbnail: {thumb_path}")
        
        return thumb_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to generate thumbnail: {str(e)}")
        return None

def get_image_metadata(image_path):
    """Extract EXIF data from image"""
    try:
        img = Image.open(image_path)
        
        # Get basic info
        metadata = {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode
        }
        
        # Try to get EXIF data
        if hasattr(img, '_getexif') and img._getexif():
            from PIL.ExifTags import TAGS
            exif = img._getexif()
            
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                metadata[tag] = value
        
        return metadata
        
    except Exception as e:
        current_app.logger.error(f"Failed to extract image metadata: {str(e)}")
        return {}

def rotate_image(image_path, degrees):
    """Rotate image by specified degrees"""
    try:
        img = Image.open(image_path)
        
        # Rotate
        rotated = img.rotate(degrees, expand=True)
        
        # Save
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            rotated.save(image_path, 'JPEG', quality=current_app.config.get('IMAGE_QUALITY', 85))
        elif image_path.lower().endswith('.png'):
            rotated.save(image_path, 'PNG', optimize=True)
        else:
            rotated.save(image_path)
        
        # Regenerate thumbnail
        generate_thumbnail(image_path)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Rotated image {degrees} degrees: {image_path}")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to rotate image: {str(e)}")
        return False