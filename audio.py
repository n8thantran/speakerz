import sounddevice as sd


def get_connected_audio_devices():
    """Get the name of the default audio output device using sounddevice."""
    try:
        device_info = sd.query_devices(kind='output')
        if not device_info:
            return "Audio: No default output device found"

        device_name = device_info.get('name', 'Unknown Device')

        # Check for bluetooth keywords and add an icon
        is_bluetooth = any(keyword in device_name.lower() for keyword in ['bluetooth', 'bt', 'wireless', 'airpods', 'headset', 'soundcore'])

        prefix = "🔵 " if is_bluetooth else ""
        return f"Audio: {prefix}{device_name}"

    except Exception as e:
        print(f"Error getting audio device: {e}")
        return "Audio: Error detecting device"


def sanitize_filename(title):
    """Make filename safe for Windows file system"""
    # Replace problematic characters
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        title = title.replace(char, '_')
    return title
