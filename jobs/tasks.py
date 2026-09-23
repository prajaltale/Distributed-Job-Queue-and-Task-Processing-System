import os
import json
import csv
import time
import hashlib
import redis
from celery import shared_task
from google import genai
from .models import Job

#'localhost' for normal runs, overridden to 'redis' automatically when running inside Docker
cache_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=1,
    decode_responses=True,
)

CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # cached results expire after 30 days
MAX_RETRIES = 3           # how many times to retry one failed Gemini call
BASE_DELAY_SECONDS = 2    # backoff pattern: 2s, then 4s, then 8s

# the instruction sent to Gemini for every single feedback row
PROMPT_TEMPLATE = """Categorize the following customer feedback into exactly one of these categories:
bug, feature-request, complaint, praise.
Also write a one-line summary of the feedback.

Respond ONLY with valid JSON in this exact format, no other text:
{{"category": "...", "summary": "..."}}

Feedback: {feedback_text}
"""


def get_cache_key(feedback_text):
    # normalize so "Great app!" and "great app! " hash to the same key
    normalized = feedback_text.strip().lower()
    return "feedback_cache:" + hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def call_gemini_with_retry(feedback_text):
    """Calls Gemini for one row, retrying with backoff. Returns a dict, never raises."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))  # created only when actually needed, not at import time
    prompt = PROMPT_TEMPLATE.format(feedback_text=feedback_text)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',  # fast, cheap model — right fit for this task
                contents=prompt,
            )
            raw_text = response.text.strip()

            try:
                parsed = json.loads(raw_text)  # convert Gemini's JSON reply into a real Python dict
            except json.JSONDecodeError:
                parsed = {"category": "unknown", "summary": raw_text}  # fallback if Gemini didn't return clean JSON

            return parsed  # success — stop retrying, return right away

        except Exception as e:
            last_error = e
            print(f"[RETRY] Attempt {attempt} failed for row: {feedback_text[:40]}... ({e})")
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))  # 2, 4, 8 seconds
                time.sleep(delay)

    # every attempt failed — return a clear failure marker instead of crashing the whole job
    return {"category": "failed", "summary": f"Failed after {MAX_RETRIES} attempts: {last_error}"}


@shared_task
def process_job(job_id):
    try:
        job = Job.objects.get(id=job_id)  # fetch the job row
        job.status = 'running'
        job.save()

        results = []  # will hold one dict per processed feedback row

        # open the uploaded CSV using its real path on disk
        with open(job.input_file.path, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)  # reads each row as a dict, keyed by the header row

            for row in reader:
                feedback_text = row.get('feedback', '').strip()  # pull the 'feedback' column
                if not feedback_text:
                    continue  # skip blank rows

                cache_key = get_cache_key(feedback_text)
                cached_value = cache_client.get(cache_key)  # check Redis for a saved result first

                if cached_value:
                    print(f"[CACHE HIT] {feedback_text[:40]}...")
                    parsed = json.loads(cached_value)
                else:
                    print(f"[CACHE MISS] Calling Gemini for: {feedback_text[:40]}...")
                    parsed = call_gemini_with_retry(feedback_text)
                    # only cache real successes — don't save "failed" results as if they were valid answers
                    if parsed.get("category") != "failed":
                        cache_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(parsed))

                results.append({
                    "feedback": feedback_text,
                    "category": parsed.get("category", "unknown"),
                    "summary": parsed.get("summary", ""),
                })

        failed_count = sum(1 for r in results if r["category"] == "failed")

        job.status = 'completed'  # the job itself finished running, even if some individual rows failed
        job.result = {
            "processed_count": len(results),
            "failed_count": failed_count,
            "items": results,
        }
        job.save()

    except Job.DoesNotExist:
        pass  # job was deleted before the worker got to it

    except Exception as e:
        # catch-all: anything goes wrong (bad CSV, API error, network issue) — mark failed instead of crashing the worker
        job = Job.objects.filter(id=job_id).first()
        if job:
            job.status = 'failed'
            job.error_message = str(e)
            job.save()