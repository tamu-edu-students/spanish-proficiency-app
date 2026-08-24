import asyncio
import json
import base64
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from django.conf import settings


class VoiceConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        self.running = False
        self.audio_queue = asyncio.Queue()
        self.session = None
        print("✓ React connected")
        await self.send(text_data=json.dumps({"status": "ready"}))

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)

            if data.get("command") == "start":
                print("✓ Starting Gemini Live session...")
                self.running = True
                asyncio.ensure_future(self.run_gemini_session())

            elif data.get("command") == "stop":
                print("✓ Stopping session")
                self.running = False

            elif "realtimeInput" in data:
                realtime_input = data["realtimeInput"]

                if "audio" in realtime_input:
                    audio_data = realtime_input["audio"]
                    if "data" in audio_data:
                        await self.audio_queue.put(audio_data["data"])
                        print(f"→ Queued audio chunk ({len(audio_data['data'])} chars)")

                if realtime_input.get("audioStreamEnd"):
                    print("✓ Audio stream ended — telling Gemini to respond")
                    if self.session:
                        try:
                            await self.session.send_realtime_input(audio_stream_end=True)
                        except Exception as e:
                            print(f"✗ Error sending stream end: {e}")

        except Exception as e:
            print(f"✗ Receive error: {e}")

    async def run_gemini_session(self):
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            config = {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Leda"
                        }
                    }
                },
                "system_instruction": (
                    "Eres un tutor de español amigable. "
                    "SIEMPRE responde en español. "
                    "Habla de forma clara y natural. "
                    "Corrige errores gramaticales amablemente."
                )
            }

            print("✓ Connecting to Gemini Live SDK...")

            async with client.aio.live.connect(
                model="gemini-2.5-flash-native-audio-preview-12-2025",
                config=config
            ) as session:
                self.session = session
                print("✓ Gemini Live session opened!")

                await self.send(text_data=json.dumps({
                    "status": "connected"
                }))

                await asyncio.gather(
                    self.send_audio(session),
                    self.receive_audio(session)
                )

        except Exception as e:
            print(f"✗ Session error: {type(e).__name__}: {e}")
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                "error": str(e)
            }))

    async def send_audio(self, session):
        """Takes audio chunks from queue and forwards to Gemini."""
        try:
            while self.running:
                try:
                    audio_b64 = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=1.0
                    )
                    print("→ Sending audio chunk to Gemini")

                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=base64.b64decode(audio_b64),
                            mime_type="audio/pcm;rate=16000"
                        )
                    )

                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            print(f"✗ Send audio error: {e}")
            traceback.print_exc()

    async def receive_audio(self, session):
        """Listens for Gemini's Spanish audio and sends to React."""
        try:
            print("✓ Now listening for Gemini responses...")
            async for response in session.receive():
                print(f"← Got response from Gemini")

                # DEBUG: show what's actually in the response
                print(f"  response.data = {response.data if hasattr(response, 'data') else 'N/A'}")
                print(f"  response.go_away = {getattr(response, 'go_away', None)}")
                print(f"  response.server_content = {getattr(response, 'server_content', None)}")

                # Try the simple .data attribute first (most common)
                if hasattr(response, 'data') and response.data:
                    print(f"  → response.data found: {len(response.data)} bytes")
                    audio_b64 = base64.b64encode(response.data).decode()
                    await self.send(text_data=json.dumps({
                        "audio": audio_b64,
                        "mimeType": "audio/pcm;rate=24000"
                    }))
                    continue

                # Check server_content for audio parts
                if response.server_content:
                    model_turn = response.server_content.model_turn
                    if model_turn and model_turn.parts:
                        for i, part in enumerate(model_turn.parts):
                            if part.inline_data and part.inline_data.data:
                                audio_b64 = base64.b64encode(
                                    part.inline_data.data
                                ).decode()
                                print(f"  ✓ Spanish audio: {len(part.inline_data.data)} bytes")
                                await self.send(text_data=json.dumps({
                                    "audio": audio_b64,
                                    "mimeType": "audio/pcm;rate=24000"
                                }))
                            if part.text:
                                print(f"  ✓ Text: {part.text}")
                                await self.send(text_data=json.dumps({
                                    "transcript": part.text
                                }))

                    if response.server_content.turn_complete:
                        print("✓ Gemini finished speaking")
                        await self.send(text_data=json.dumps({
                            "turnComplete": True
                        }))

        except Exception as e:
            print(f"✗ Receive audio error: {type(e).__name__}: {e}")
            traceback.print_exc()

    async def disconnect(self, close_code):
        print("✓ React disconnected")
        self.running = False
        self.session = None