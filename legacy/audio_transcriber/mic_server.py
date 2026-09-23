from fastapi import FastAPI, Request, Response
import numpy as np
import whisper
import tempfile
import wave
import uvicorn
import os
from gtts import gTTS
from io import BytesIO
import soundfile as sf
import librosa

# Configurar logging con colores
class ColorLogger:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    
    @staticmethod
    def info(msg):
        print(f"{ColorLogger.BLUE}[INFO] {msg}{ColorLogger.ENDC}")
    
    @staticmethod
    def success(msg):
        print(f"{ColorLogger.GREEN}[SUCCESS] {msg}{ColorLogger.ENDC}")
    
    @staticmethod
    def warning(msg):
        print(f"{ColorLogger.YELLOW}[WARN] {msg}{ColorLogger.ENDC}")
    
    @staticmethod
    def error(msg):
        print(f"{ColorLogger.RED}[ERROR] {msg}{ColorLogger.ENDC}")

# Configuration
RATE = 16000
MIN_AUDIO_LENGTH = 0.2

app = FastAPI()

# Cargar modelo Whisper
print("\n" + "="*50)
ColorLogger.info("Cargando modelo Whisper...")
model = whisper.load_model("base")
ColorLogger.success("Whisper model loaded successfully.")
print("="*50 + "\n")

class AudioBuffer:
    def __init__(self):
        self.buffer = np.array([], dtype=np.int16)
        self.recording = False
        self.process_pending = False
        self.last_audio_level = 0
        ColorLogger.info("Sistema inicializado y esperando audio...")

    def add_audio(self, audio_data: np.ndarray):
        audio_level = np.max(np.abs(audio_data))
        self.last_audio_level = audio_level
        self.buffer = np.append(self.buffer, audio_data)
        seconds = len(self.buffer)/RATE
        print(f"\r📊 Estado: Grabando... {seconds:.1f} segundos | "
              f"Nivel de audio: {audio_level:4d} | "
              f"Buffer: {len(self.buffer):6d} muestras", end='')
    
    def should_process(self):
        if not self.recording and self.process_pending:
            print("\n" + "="*50)
            ColorLogger.info("🛑 GRABACIÓN FINALIZADA")
            return True
        return False
    
    def get_and_clear(self):
        if self.should_process():
            if len(self.buffer) > RATE * MIN_AUDIO_LENGTH:
                seconds = len(self.buffer)/RATE
                ColorLogger.info(f"⚙️ Procesando {seconds:.1f} segundos de audio...")
                audio = self.buffer.copy()
                max_val = np.max(np.abs(audio))
                if max_val > 0:
                    audio = (audio / max_val * 32767).astype(np.int16)
                self.buffer = np.array([], dtype=np.int16)
                self.process_pending = False
                return audio
            else:
                ColorLogger.warning("❌ Audio muy corto, descartando...")
                self.buffer = np.array([], dtype=np.int16)
                self.process_pending = False
        return None

audio_buffer = AudioBuffer()

def text_to_speech(text: str) -> bytes:
    """Convierte texto a audio usando gTTS y lo prepara para I2S"""
    try:
        ColorLogger.info("🔊 Generando audio con TTS...")
        # Usar BytesIO para evitar escribir archivos temporales
        tts = gTTS(text=text, lang='es', slow=False)
        mp3_buffer = BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        
        # Cargar MP3 directamente desde el buffer
        audio_data = BytesIO(mp3_buffer.read())
        y, sr = librosa.load(audio_data, sr=16000)
        
        # Normalizar y convertir a int16
        y = np.clip(y, -1.0, 1.0)
        audio_16bit = (y * 32767).astype(np.int16)
        
        # Crear WAV en memoria
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_16bit.tobytes())
        
        ColorLogger.success("✨ Audio TTS generado correctamente")
        return wav_buffer.getvalue()
    
    except Exception as e:
        ColorLogger.error(f"Error en TTS: {str(e)}")
        return None

@app.post("/audio")
async def receive_audio(request: Request):
    try:
        # Check whether this is the end-of-recording signal
        if request.headers.get("Recording-Status") == "end":
            ColorLogger.info("End-of-recording signal received")
            audio_buffer.recording = False
            audio_buffer.process_pending = True
            audio_to_process = audio_buffer.get_and_clear()
            
            if audio_to_process is not None:
                # Crear archivo WAV temporal para whisper
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    wav_path = temp_wav.name
                    with wave.open(wav_path, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(RATE)
                        wav_file.writeframes(audio_to_process.tobytes())
                    
                    try:
                        # Transcribir con Whisper
                        ColorLogger.info("🔄 Transcribiendo audio...")
                        result = model.transcribe(wav_path, language='es')
                        transcription = result["text"].strip()
                        
                        if transcription:
                            print("\n" + "="*50)
                            ColorLogger.success("✨ TRANSCRIPCIÓN COMPLETADA")
                            print(f"📝 Texto: {transcription}")
                            print("="*50)
                            
                            # Convert the transcription to audio
                            audio_response = text_to_speech(transcription)
                            if audio_response:
                                return Response(
                                    content=audio_response,
                                    media_type="audio/wav"
                                )
                        else:
                            ColorLogger.warning("No text detected in the audio")
                            
                    finally:
                        try:
                            os.unlink(wav_path)
                        except:
                            pass
                            
            return {"status": "ok"}
            
        # Procesar audio entrante
        audio_data = await request.body()
        if len(audio_data) == 0:
            return {"status": "ok"}
            
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        audio_buffer.add_audio(audio_array)
        
        return {"status": "ok"}
        
    except Exception as e:
        ColorLogger.error(f"Error: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("\n" + "="*50)
    ColorLogger.success("Transcription server started")
    ColorLogger.info("👂 Esperando audio...")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)