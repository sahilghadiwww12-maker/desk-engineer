import os
import io
import json
import re
import time
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from google import genai
from google.genai import types

app = FastAPI()           

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ Paste your Gemini API key here
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6K5b1c_VliIFzsr4ekLN9UJoyGdGeGaTJYh237VT_7buQ")
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are an expert multi-disciplinary quality control engineer and blueprint diagnostician covering Electrical, Electronics, and Mechanical Engineering.
Examine this blueprint, CAD drawing, PCB, or hardware photo carefully.

Auto-detect the domain:
1. If ELECTRICAL / ELECTRONICS:
   - Identify missing or incorrect components, reverse polarities (LEDs, diodes, IC pin 1, electrolytic caps).
   - Check for short circuits, floating nets, missing base resistors, or solder bridges.

2. If MECHANICAL / CAD / P&ID (Hydraulics & Pneumatics):
   - Identify missing critical dimensions, redundant dimension chains, or under-constrained geometries.
   - Flag sharp interior corners lacking stress-relief fillets in high-load areas.
   - Check mechanical fasteners, thread specs, bearing seating, and interference fit issues.
   - For fluid/pneumatic schematics, identify reversed check valves, missing relief valves, or unvented lines.

CRITICAL INSTRUCTION:
For EVERY defect found, you MUST provide an explicit, actionable engineering SOLUTION (practical step-by-step fix).
Provide normalized bounding box coordinates on a 0-1000 scale: [ymin, xmin, ymax, xmax].

Return strictly raw JSON (no markdown, no backticks):
{
  "domain": "ELECTRICAL" or "MECHANICAL",
  "status": "PASS" or "FAIL",
  "summary": "1-2 sentence executive verdict",
  "defects": [
    {
      "component": "e.g., Shaft Bearing Fit, Fillet Radius R2, or Diode D1",
      "issue": "Detailed description of the defect or design flaw",
      "severity": "CRITICAL" or "WARNING",
      "solution": "Clear, practical engineering fix",
      "box_2d": [ymin, xmin, ymax, xmax]
    }
  ]
}
"""

PRIORITY_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash"
]

@app.post("/inspect")
async def inspect_board(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents))
    last_error = "Unknown error"

    for model_name in PRIORITY_MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[image, "Inspect this engineering blueprint or hardware. Auto-detect domain (electrical/mechanical), identify all defects with bounding boxes, and give exact solutions."],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json"
                    )
                )

                raw_text = response.text.strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
                raw_text = re.sub(r"\s*```$", "", raw_text, flags=re.MULTILINE)
                return json.loads(raw_text)

            except Exception as e:
                last_error = str(e)
                if "503" in last_error or "UNAVAILABLE" in last_error:
                    time.sleep(1.2)
                    continue
                else:
                    break

    return {
        "status": "FAIL",
        "summary": "API traffic peak. Please retry shortly.",
        "defects": [
            {
                "component": "API Gateway",
                "issue": last_error,
                "severity": "WARNING",
                "solution": "Wait 10-15 seconds and re-inspect to bypass temporary traffic congestion.",
                "box_2d": [100, 100, 300, 300]
            }
        ]
    }

    app.mount("/", StaticFiles(directory="static", html=True), name="static")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

