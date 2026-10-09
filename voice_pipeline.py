import json
import os
import queue
import time
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from google import genai
from google.genai import types
from kokoro import KPipeline
import numpy as np
import sounddevice as sd
import torch
from datetime import datetime

load_dotenv()

SAMPLE_RATE = 16000
FRAME_SIZE = 512
VAD_THRESHOLD = 0.5
SILENCE_DURATION_LIMIT = 0.55  

audio_queue = queue.Queue()
is_agent_speaking = False  


def audio_input_callback(indata, frames, time_info, status):
  if not is_agent_speaking:
    audio_queue.put(indata[:, 0].copy())


# 1. Models Initialization
print("--> [1/4] Loading Silero VAD...")
vad_model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-vad", model="silero_vad", onnx=False
)

print("--> [2/4] Loading Distil-Whisper with CPU optimization...")
whisper = WhisperModel(
    "base.en",
    device="cpu",
    compute_type="int8",
    cpu_threads=6,  # Adjust to your physical core count
    num_workers=1,
)

print("--> [3/4] Loading Kokoro TTS...")
tts = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")

print("--> [4/4] Initializing Gemini Client...")
gemini_client = genai.Client()


# 2. Tool Definitions
def schedule_meeting(doctor: str, date: str, time: str, purpose: str) -> str:
  print(
      f"\n[ACTION: TOOL EXECUTED] schedule_meeting -> {doctor} | {date} |"
      f" {time} | {purpose}"
  )
  return json.dumps({
      "status": "success",
      "doctor": doctor,
      "date": date,
      "time": time,
  })


today_str = datetime.now().strftime("%A, %B %d, %Y")
# 3. Gemini Chat Initialization
system_instruction = f"""You are an AI medical voice scheduling assistant.
Today's date is {today_str}.

Rules:
1. Resolve relative dates like 'tomorrow' using today's date.
2. SPOKEN TEXT FORMATTING: Write out times, titles, and dates in conversational spoken English. 
   - Write '10:00 AM' as '10 AM' or 'ten in the morning'.
   - Write '2:30 PM' as '2:30 PM' or 'two thirty PM'.
   - Write 'Dr.' as 'Doctor'.
3. Keep spoken responses under 2 sentences."""


chat_session = gemini_client.chats.create(
    model="gemini-3.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1,
        tools=[schedule_meeting],
    ),
)


# 4. Echo-Safe TTS Playback
def speak(text: str):
  global is_agent_speaking
  is_agent_speaking = True  # Stop recording input while speaking

  # Drain any audio accumulated right before speech starts
  while not audio_queue.empty():
    try:
      audio_queue.get_nowait()
    except queue.Empty:
      break

  print(f"[Agent Speaking]: {text}")
  generator = tts(text, voice="af_bella", speed=1.0)
  chunks = [audio for _, _, audio in generator]
  if chunks:
    full_audio = np.concatenate(chunks)
    sd.play(full_audio, 24000)
    sd.wait()

  # Flush out echo/reverberations picked up during playback
  time.sleep(0.1)
  while not audio_queue.empty():
    try:
      audio_queue.get_nowait()
    except queue.Empty:
      break

  vad_model.reset_states()
  is_agent_speaking = False  # Unmute microphone


# 5. Main Execution Loop
def main():
  print("\n=======================================================")
  print("Voice Scheduling Agent is LIVE. Speak into your mic...")
  print("=======================================================\n")

  speak(
      "Hello, I am an AI scheduling assistant. How can I help you manage your"
      " appointments?"
  )

  is_user_speaking = False
  speech_frames = []
  silence_started_at = None

  with sd.InputStream(
      samplerate=SAMPLE_RATE,
      channels=1,
      dtype="float32",
      blocksize=FRAME_SIZE,
      callback=audio_input_callback,
  ):
    while True:
      try:
        frame = audio_queue.get(timeout=0.05)
      except queue.Empty:
        continue

      tensor_frame = torch.from_numpy(frame)
      speech_prob = vad_model(tensor_frame, SAMPLE_RATE).item()

      if speech_prob > VAD_THRESHOLD:
        if not is_user_speaking:
          is_user_speaking = True
          print("\n[VAD]: User speaking...")
        speech_frames.append(frame)
        silence_started_at = None
      else:
        if is_user_speaking:
          speech_frames.append(frame)
          if silence_started_at is None:
            silence_started_at = time.time()
          elif time.time() - silence_started_at > SILENCE_DURATION_LIMIT:
            print("[VAD]: Speech pause detected. Transcribing...")
            turn_audio = np.concatenate(speech_frames)

            # Reset tracking
            is_user_speaking = False
            speech_frames = []
            silence_started_at = None
            vad_model.reset_states()

            t0 = time.time()
            segments, _ = whisper.transcribe(
                turn_audio,
                language="en",
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            transcript = " ".join([s.text for s in segments]).strip()
            stt_latency = round((time.time() - t0) * 1000)

            if transcript:
              print(f"[User Said ({stt_latency}ms)]: '{transcript}'")

              # LLM Processing
              t_llm = time.time()
              response = chat_session.send_message(transcript)
              llm_latency = round((time.time() - t_llm) * 1000)
              agent_reply = response.text or ""
              print(f"[Gemini Output ({llm_latency}ms)]: '{agent_reply}'")

              if agent_reply:
                speak(agent_reply)

            print("\n[Listening for next response...]")


if __name__ == "__main__":
  main()