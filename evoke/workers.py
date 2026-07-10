import json
import datetime
import asyncio
from io import BytesIO
from pypdf import PdfReader
from kafka import KafkaConsumer
from clients import s3_client, os_client, ai_client, get_producer, REDPANDA_BROKER, AI_ENABLED, AI_MODEL

def generate_ai_insight(preview_text: str) -> str:

    if not AI_ENABLED or ai_client is None:
        return (
            "AI is disabled for this installation. "
            "Great job submitting your evidence. An instructor can review it later."
        )

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an empathetic learning coach..."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Student submission:\n{preview_text}",
                },
            ],
            max_tokens=150,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"AI unavailable: {e}")

        return (
            "AI feedback is temporarily unavailable. "
            "Your submission has been received successfully."
        )
        
async def evoke_workers_loop():
    await asyncio.sleep(5)
    
    try:
        consumer = KafkaConsumer(
            'evoke-events',
            bootstrap_servers=[REDPANDA_BROKER],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        producer = get_producer()
        print(">>> Independent EVOKE background workers started listening to stream.")
        
        while True:
            msg_pack = consumer.poll(timeout_ms=500)
            for tp, messages in msg_pack.items():
                for message in messages:
                    event = message.value
                    event_type = event.get("event_type")
                    
                    # -------------------------------------------------------------
                    # 1. AI COACH WORKER
                    # -------------------------------------------------------------
                    if event_type in ["EvidenceSubmitted", "TeamEvidenceSubmitted"]:
                        
                        object_key = event['data']['object_key']
                        mission_id = event['data']['mission_id']
                        
                        # Handle individual vs team payload structure
                        if event_type == "EvidenceSubmitted":
                            learners_to_update = [event['data']['learner_id']]
                        else:
                            learners_to_update = event['data']['team_members']
                        
                        print(f"[AI WORKER] Fetching payload {object_key} for {len(learners_to_update)} learners...")
                        
                        try:
                            response = s3_client.get_object(Bucket="default-bucket", Key=object_key)
                            reader = PdfReader(BytesIO(response['Body'].read()))
                            extracted_text = "".join([page.extract_text() + "\n" for page in reader.pages])[:3000]
                            ai_response = generate_ai_insight(extracted_text)
                        except Exception as e:
                            print(f"[AI WORKER ERROR] Failed to parse file payload: {e}")
                            ai_response = "Error parsing document. Please confirm it is a readable PDF layout."
                        
                        # Publish feedback for EVERY learner on the team independently
                        for learner_id in learners_to_update:
                            feedback_event = {
                                "event_type": "FeedbackGenerated",
                                "version": "1.0.0",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "data": {
                                    "learner_id": learner_id,
                                    "mission_id": mission_id,
                                    "insight": {
                                        "category": "Suggestion",
                                        "source": "AI Coach",
                                        "text": ai_response
                                    }
                                }
                            }
                            producer.send('evoke-events', value=feedback_event)
                            
                        producer.flush()
                        print(f"[AI WORKER] Dispatched AI Insights for {len(learners_to_update)} learners.")
                    
                    # -------------------------------------------------------------
                    # 2. SEARCH & TIMELINE WORKER
                    # -------------------------------------------------------------
                    elif event_type in ["FeedbackGenerated", "InsightPublished"]:
                        learner_id = event['data']['learner_id']
                        mission_id = event['data']['mission_id']
                        new_insight = event['data']['insight']
                        
                        projection_id = f"{learner_id}_{mission_id}"
                        now_str = datetime.datetime.now().isoformat()
                        
                        try:
                            current = os_client.get(index="learner-timeline", id=projection_id)['_source']
                        except Exception:
                            current = {"learner_id": learner_id, "mission_id": mission_id, "insights": [], "timeline": []}
                        
                        if "insights" not in current:
                            current["insights"] = []
                        current["insights"].append(new_insight)
                        
                        # Logic to advance the specific timeline steps based on who provided feedback
                        for step in current.get("timeline", []):
                            if event_type == "FeedbackGenerated":
                                if step["id"] == "processing":
                                    step["status"] = "completed"
                                    step["content"] = "Text extracted and routed successfully."
                                elif step["id"] == "ai_analysis":
                                    step["status"] = "completed"
                                    step["timestamp"] = now_str
                                    step["content"] = f"<strong>[{new_insight['category']} from {new_insight['source']}]</strong><br/>{new_insight['text']}"
                                elif step["id"] == "teacher_review":
                                    step["status"] = "active"
                                    
                            elif event_type == "InsightPublished":
                                current["status"] = "Human Review Received"
                                if step["id"] == "teacher_review":
                                    step["status"] = "completed"
                                    step["timestamp"] = now_str
                                    # Append human feedback to the timeline step directly
                                    existing = step["content"] if step["content"] != "Awaiting human insights." else ""
                                    step["content"] = existing + f"<br/><br/><strong>[{new_insight['category']} from {new_insight['source']}]</strong><br/>{new_insight['text']}"

                        os_client.index(index="learner-timeline", id=projection_id, body=current, refresh=True)
                        print(f"[SEARCH WORKER] Projected {event_type} into read-model for {learner_id}.")
                        
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"Fatal worker pipeline event loop crash: {e}")