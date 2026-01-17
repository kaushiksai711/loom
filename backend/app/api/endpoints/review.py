"""
Phase 15: Spaced Repetition Review Endpoints
Handles review queue and SM-2 scheduling.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from backend.app.db.arango import db

router = APIRouter()


class AssessRequest(BaseModel):
    """Request body for assessing a concept during review."""
    difficulty: str  # "hard" | "good" | "easy"
    mastered: bool = False  # If true, set mastery to 0.95 and long interval


# SM-2 Algorithm Constants
SM2_INTERVALS = {
    "hard": 2,    # Days
    "good": 7,
    "easy": 14,
    "mastered": 30  # Phase 15.1: "I've mastered this" option
}

SM2_MASTERY_BOOST = {
    "hard": 0.0,   # No boost for hard
    "good": 0.05,
    "easy": 0.10,
    "mastered": 0.85  # Boost to 0.95+ for mastered
}


@router.get("/queue")
async def get_review_queue(limit: int = 20):
    """
    Returns concepts due for review.
    Only includes concepts where scaffold was generated (user clicked "Learn This").
    
    Sorted by next_review ASC (most overdue first).
    """
    try:
        arango_db = db.get_db()
        
        # Ensure Concepts collection exists
        if not arango_db.has_collection("Concepts"):
            return {"concepts": [], "total_due": 0}
        
        aql = """
        LET now = DATE_ISO8601(DATE_NOW())
        
        FOR c IN Concepts
            FILTER c.scaffold_generated == true
            FILTER c.next_review != null
            FILTER c.next_review <= now
            SORT c.next_review ASC
            LIMIT @limit
            
            // Get session info for context
            LET session = (
                FOR s IN Sessions
                    FILTER s._key == c.origin_session
                    LIMIT 1
                    RETURN s.title
            )[0]
            
            RETURN {
                _id: c._id,
                _key: c._key,
                label: c.label,
                definition: c.definition,
                mastery: c.mastery || 0.1,
                next_review: c.next_review,
                last_reviewed: c.last_reviewed,
                review_count: c.review_count || 0,
                origin_session: c.origin_session,
                session_title: session || "Unknown Session"
            }
        """
        
        concepts = list(arango_db.aql.execute(aql, bind_vars={"limit": limit}))
        
        # Also get total count of due concepts
        count_aql = """
        LET now = DATE_ISO8601(DATE_NOW())
        FOR c IN Concepts
            FILTER c.scaffold_generated == true
            FILTER c.next_review != null
            FILTER c.next_review <= now
            COLLECT WITH COUNT INTO total
            RETURN total
        """
        total_due = list(arango_db.aql.execute(count_aql))[0] if concepts else 0
        
        return {
            "concepts": concepts,
            "total_due": total_due,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assess/{concept_id:path}")
async def assess_concept(concept_id: str, request: AssessRequest):
    """
    Update concept's next_review based on SM-2 algorithm.
    
    Difficulty options:
    - "hard": Review in 2 days, no mastery boost
    - "good": Review in 7 days, +0.05 mastery
    - "easy": Review in 14 days, +0.10 mastery
    """
    try:
        arango_db = db.get_db()
        
        # Validate difficulty
        if request.difficulty not in SM2_INTERVALS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid difficulty. Must be one of: {list(SM2_INTERVALS.keys())}"
            )
        
        # Get current concept
        key = concept_id.split("/")[-1] if "/" in concept_id else concept_id
        concept = arango_db.collection("Concepts").get(key)
        
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        
        # Handle "mastered" flag
        difficulty = "mastered" if request.mastered else request.difficulty
        
        # Calculate new values
        interval_days = SM2_INTERVALS[difficulty]
        mastery_boost = SM2_MASTERY_BOOST[difficulty]
        
        current_mastery = concept.get("mastery", 0.1)
        new_mastery = min(1.0, current_mastery + mastery_boost)
        
        # For mastered, ensure at least 0.95
        if request.mastered:
            new_mastery = max(0.95, new_mastery)
        
        new_next_review = (datetime.utcnow() + timedelta(days=interval_days)).isoformat()
        new_review_count = (concept.get("review_count") or 0) + 1
        
        # Update concept
        arango_db.collection("Concepts").update({
            "_key": key,
            "mastery": new_mastery,
            "next_review": new_next_review,
            "last_reviewed": datetime.utcnow().isoformat(),
            "review_count": new_review_count
        })
        
        print(f"[Phase 15] Assessed {concept_id}: {request.difficulty} -> next in {interval_days}d, mastery={new_mastery:.2f}")
        
        return {
            "status": "success",
            "concept_id": concept_id,
            "difficulty": request.difficulty,
            "interval_days": interval_days,
            "new_mastery": new_mastery,
            "next_review": new_next_review,
            "review_count": new_review_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_review_stats():
    """
    Returns review statistics for the user.
    """
    try:
        arango_db = db.get_db()
        
        if not arango_db.has_collection("Concepts"):
            return {"total_learned": 0, "due_now": 0, "mastered": 0}
        
        aql = """
        LET now = DATE_ISO8601(DATE_NOW())
        LET all_learned = (FOR c IN Concepts FILTER c.scaffold_generated == true RETURN c)
        LET due = (FOR c IN all_learned FILTER c.next_review <= now RETURN c)
        LET mastered = (FOR c IN all_learned FILTER c.mastery >= 0.9 RETURN c)
        
        RETURN {
            total_learned: LENGTH(all_learned),
            due_now: LENGTH(due),
            mastered: LENGTH(mastered)
        }
        """
        
        result = list(arango_db.aql.execute(aql))
        return result[0] if result else {"total_learned": 0, "due_now": 0, "mastered": 0}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming")
async def get_upcoming_reviews(limit: int = 20):
    """
    Returns concepts scheduled for review in the future.
    Ordered by next_review date (soonest first).
    """
    try:
        arango_db = db.get_db()
        
        if not arango_db.has_collection("Concepts"):
            return {"upcoming": []}
        
        aql = """
        LET now = DATE_ISO8601(DATE_NOW())
        
        FOR c IN Concepts
            FILTER c.scaffold_generated == true
            FILTER c.next_review != null
            FILTER c.next_review > now
            SORT c.next_review ASC
            LIMIT @limit
            
            RETURN {
                _id: c._id,
                label: c.label,
                mastery: c.mastery || 0.1,
                next_review: c.next_review,
                session_title: c.origin_session || "Unknown"
            }
        """
        
        upcoming = list(arango_db.aql.execute(aql, bind_vars={"limit": limit}))
        
        return {"upcoming": upcoming}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
