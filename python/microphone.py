import time
import numpy as np
import config

try:
    import pyaudio
except Exception as exc:
    # Friendly error message if PyAudio isn't installed or fails to import
    msg = (
        "PyAudio is not installed or failed to import.\n"
        "This module is required to capture audio from the microphone.\n"
        "On Debian/Raspberry Pi, install system deps then install PyAudio in your venv:\n"
        "  sudo apt update && sudo apt install -y portaudio19-dev libasound2-dev python3-dev build-essential\n"
        "  python3 -m pip install --upgrade pip setuptools wheel\n"
        "  python3 -m pip install pyaudio\n"
        "Or install the Debian package: sudo apt install python3-pyaudio\n"
    )
    print(msg)
    raise


def start_stream(callback):
    p = pyaudio.PyAudio()
    frames_per_buffer = int(config.MIC_RATE / config.FPS)
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=config.MIC_RATE,
                    input=True,
                    frames_per_buffer=frames_per_buffer)
    overflows = 0
    prev_ovf_time = time.time()
    while True:
        try:
            y = np.fromstring(stream.read(frames_per_buffer, exception_on_overflow=False), dtype=np.int16)
            y = y.astype(np.float32)
            stream.read(stream.get_read_available(), exception_on_overflow=False)
            callback(y)
        except IOError:
            overflows += 1
            if time.time() > prev_ovf_time + 1:
                prev_ovf_time = time.time()
                print('Audio buffer has overflowed {} times'.format(overflows))
    stream.stop_stream()
    stream.close()
    p.terminate()
