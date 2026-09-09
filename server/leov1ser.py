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
from openai import OpenAI
import time
import json
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Gestión del contexto de conversación
class ConversationContext:
    def __init__(self):
        self.context = []
        self.max_context_length = 5
        self.context_token_limit = 1000
    
    def gestionar_contexto(self, mensaje, role="user"):
        """Gestiona el contexto de la conversación"""
        self.context.append({
            "role": role,
            "content": mensaje,
            "timestamp": time.time()
        })
        
        if len(self.context) > self.max_context_length * 2:
            self.context = self.context[-self.max_context_length * 2:]
            
    def obtener_contexto_relevante(self, pregunta_actual):
        """Obtiene el contexto relevante para la pregunta actual"""
        contexto_relevante = []
        for msg in self.context[-6:]:
            contexto_relevante.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return contexto_relevante
    
    def limpiar_contexto(self):
        """Limpia el contexto de la conversación"""
        self.context = []

conversation_context = ConversationContext()

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

# Configuración
RATE = 16000
MIN_AUDIO_LENGTH = 0.2

app = FastAPI()

# Cargar modelo Whisper
print("\n" + "="*50)
ColorLogger.info("Cargando modelo Whisper...")
model = whisper.load_model("base")
ColorLogger.success("¡Modelo Whisper cargado exitosamente!")
print("="*50 + "\n")

def get_openai_response(prompt):
    """Obtiene respuestas adaptativas de OpenAI API con contexto"""
    conversation_context.gestionar_contexto(prompt, "user")
    
    prompt_sistema = """Eres un asistente que da respuestas precisas y completas.
    MUY IMPORTANTE: 
    - Tus respuestas NO DEBEN exceder las 50-60 palabras
    - SIEMPRE termina las oraciones con punto o signo de puntuación
    - Si el tema requiere una respuesta más larga, da una versión resumida
    - Usa frases cortas y directas
    - Prioriza claridad y concisión sobre detalles
    - Evita palabras innecesarias y redundancias"""
    
    messages = [
        {"role": "system", "content": prompt_sistema},
        {"role": "system", "content": "Recuerda: Adapta tu respuesta al espacio y SIEMPRE completa tus oraciones."},
        *conversation_context.obtener_contexto_relevante(prompt),
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5,
            max_tokens=100,
            presence_penalty=0.6,
            frequency_penalty=0.6
        )
        
        respuesta = response.choices[0].message.content.strip()
        
        # Verificar que la respuesta termine en un punto o signo de puntuación
        if not any(respuesta.endswith(signo) for signo in ['.', '!', '?', ':', ';']):
            messages.append({"role": "system", "content": "La respuesta anterior era demasiado larga. Da una versión más concisa pero completa."})
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.5,
                max_tokens=100,
                presence_penalty=0.8,
                frequency_penalty=0.8
            )
            respuesta = response.choices[0].message.content.strip()
        
        conversation_context.gestionar_contexto(respuesta, "assistant")
        return respuesta
        
    except Exception as e:
        ColorLogger.error(f"Error en OpenAI: {str(e)}")
        return "Lo siento, hubo un error al procesar tu pregunta."

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
    """Convierte texto a audio usando gTTS"""
    try:
        ColorLogger.info("🔊 Generando audio con TTS...")
        tts = gTTS(text=text, lang='es', slow=False)
        mp3_buffer = BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        
        audio_data = BytesIO(mp3_buffer.read())
        y, sr = librosa.load(audio_data, sr=16000)
        
        y = np.clip(y, -1.0, 1.0)
        audio_16bit = (y * 32767).astype(np.int16)
        
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
        # Verificar si es señal de fin de grabación
        if request.headers.get("Recording-Status") == "end":
            ColorLogger.info("Señal de fin de grabación recibida")
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
                            print(f"📝 Texto transcrito: {transcription}")
                            
                            # Obtener respuesta de OpenAI
                            ColorLogger.info("🤖 Consultando a OpenAI...")
                            ai_response = get_openai_response(transcription)
                            print(f"🤖 Respuesta de OpenAI: {ai_response}")
                            
                            # Convertir respuesta a audio
                            audio_response = text_to_speech(ai_response)
                            if audio_response:
                                # Agregar headers específicos para evitar problemas de buffering
                                headers = {
                                    "Content-Type": "audio/wav",
                                    "Content-Length": str(len(audio_response)),
                                    "Connection": "close",
                                    "Cache-Control": "no-cache"
                                }
                                return Response(
                                    content=audio_response,
                                    media_type="audio/wav",
                                    headers=headers
                                )
                        else:
                            ColorLogger.warning("⚠️ No se detectó texto en el audio")
                            
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
    ColorLogger.success("🚀 Servidor de transcripción iniciado")
    ColorLogger.info("👂 Esperando audio...")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)