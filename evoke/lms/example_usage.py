"""
Example usage of BrightspaceLMS adapter.

This shows how to use the production Brightspace integration in your application.
"""

import asyncio
import asyncpg
from evoke.lms import BrightspaceLMS


async def example_submission_workflow():
    """
    Example: Student submits evidence, we sync to Brightspace.

    This would be called from POST /api/submit-evidence endpoint.
    """
    # Initialize adapter (usually done once at app startup)
    db_pool = await asyncpg.create_pool(
        "postgresql://evoke:devsecret123@localhost:5432/evoke"
    )

    lms = BrightspaceLMS(
        tenant_url="https://school.brightspace.com",
        app_key="your-app-key",
        app_secret="your-app-secret",
        org_unit_id="12345",
        db_pool=db_pool,
    )

    try:
        # User submits evidence
        evoke_user_id = "ac29d0ec-508b-4ae3-9a0f-1a090d924f29"
        mission_id = "a4e2ff87-65a1-4d8e-8fda-350add075e4a"
        submission_id = "2c822270-8c08-4db8-a194-d0999234ec23"

        file_name = "mission-response.pdf"
        file_content = b"PDF content here..."

        # 1. Submit to Brightspace
        bs_submission_id = await lms.submit_assignment(
            evoke_user_id=evoke_user_id,
            mission_id=mission_id,
            file_name=file_name,
            file_content=file_content,
            submission_id=submission_id,
        )

        if bs_submission_id:
            print(f"✓ Submitted to Brightspace: {bs_submission_id}")
        else:
            print("✗ Failed to submit to Brightspace")
            return

        # 2. Award badge for submission (auto-awarded)
        badge_id = "539a92d0-d5be-400d-84bf-a1d8a35eba2a"  # Common tier
        campaign_id = "campaign-uuid"

        success = await lms.push_badge_award(
            evoke_user_id=evoke_user_id,
            badge_id=badge_id,
            campaign_id=campaign_id,
            criteria="Submitted evidence for mission",
            evidence=f"Submission ID: {bs_submission_id}",
        )

        if success:
            print("✓ Badge awarded in Brightspace")
        else:
            print("✗ Failed to award badge")

    finally:
        await lms.close()
        await db_pool.close()


async def example_grading_workflow():
    """
    Example: Teacher grades in Brightspace, we sync back to EVOKE.

    This would be called from webhook or polling mechanism (Task 4.1).
    """
    db_pool = await asyncpg.create_pool(
        "postgresql://evoke:devsecret123@localhost:5432/evoke"
    )

    lms = BrightspaceLMS(
        tenant_url="https://school.brightspace.com",
        app_key="your-app-key",
        app_secret="your-app-secret",
        org_unit_id="12345",
        db_pool=db_pool,
    )

    try:
        # Teacher grades submission
        submission_id = "2c822270-8c08-4db8-a194-d0999234ec23"
        grade = 95
        feedback = "Excellent work! Very thorough analysis."

        success = await lms.push_mission_status(
            evoke_user_id="ac29d0ec-508b-4ae3-9a0f-1a090d924f29",
            submission_id=submission_id,
            grade=grade,
            feedback=feedback,
        )

        if success:
            print(f"✓ Grade updated: {grade}")

            # Now award legendary badge (high grade)
            legendary_badge_id = "8a737953-f3e0-41f9-9311-9d3e99a6713e"
            campaign_id = "campaign-uuid"

            success = await lms.push_badge_award(
                evoke_user_id="ac29d0ec-508b-4ae3-9a0f-1a090d924f29",
                badge_id=legendary_badge_id,
                campaign_id=campaign_id,
                criteria=f"Teacher graded submission: {grade}/100",
                evidence=f"Submission ID: {submission_id}",
            )

            if success:
                print("✓ Legendary badge awarded")

    finally:
        await lms.close()
        await db_pool.close()


async def example_polling_grades():
    """
    Example: Poll Brightspace for new grades and sync back.

    This runs periodically to catch grades that might have been missed
    by webhook (Task 4.1 - Polling fallback).
    """
    db_pool = await asyncpg.create_pool(
        "postgresql://evoke:devsecret123@localhost:5432/evoke"
    )

    lms = BrightspaceLMS(
        tenant_url="https://school.brightspace.com",
        app_key="your-app-key",
        app_secret="your-app-secret",
        org_unit_id="12345",
        db_pool=db_pool,
    )

    try:
        assignment_id = "m1"  # Follow the Flow mission

        # Get all submissions for this assignment
        submissions = await lms.get_submissions_for_assignment(assignment_id)

        if not submissions:
            print("No submissions found")
            return

        print(f"Found {len(submissions)} submissions")

        # Process each submission
        for sub in submissions:
            bs_submission_id = sub.get("SubmissionId")
            grade = sub.get("Grade")
            status = sub.get("Status", "submitted")

            # Check if graded
            if status == "graded" and grade is not None:
                print(f"Submission {bs_submission_id}: Graded {grade}")
                # TODO: Match to EVOKE submission and update
            else:
                print(f"Submission {bs_submission_id}: {status}")

    finally:
        await lms.close()
        await db_pool.close()


if __name__ == "__main__":
    print("=== Example 1: Submission Workflow ===")
    asyncio.run(example_submission_workflow())

    print("\n=== Example 2: Grading Workflow ===")
    asyncio.run(example_grading_workflow())

    print("\n=== Example 3: Polling Grades ===")
    asyncio.run(example_polling_grades())
