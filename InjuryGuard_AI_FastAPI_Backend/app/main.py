from pathlib import Path
from datetime import datetime, date, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from sqlmodel import SQLModel, Field, Session, create_engine, select

from app.fracture_predictor import predict_fracture
from app.video_predictor import predict_video


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{BASE_DIR / 'injuryguard.db'}"

engine = create_engine(
    DATABASE_URL,
    echo=False
)


# ============================================================
# DATABASE MODEL
# ============================================================

class Assessment(SQLModel, table=True):

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    # --------------------------------------------------------
    # ATHLETE INFORMATION
    # --------------------------------------------------------

    athlete_name: Optional[str] = None
    athlete_email: Optional[str] = None
    athlete_age: Optional[str] = None
    athlete_gender: Optional[str] = None
    athlete_blood_group: Optional[str] = None
    athlete_phone: Optional[str] = None

    # --------------------------------------------------------
    # ASSESSMENT INFORMATION
    # --------------------------------------------------------

    sport: str
    intensity: str
    previous_injury: str
    recovery_days: int

    injury_date: Optional[str] = None
    xray_date: Optional[str] = None
    days_since_injury: Optional[int] = None

    pain_location: str
    pain_level: int

    muscle_condition: str
    ligament_stability: str
    mental_readiness: str
    sleep_quality: str

    feedback: str

    media_filename: Optional[str] = None

    risk_score: int
    risk_level: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def create_db():
    SQLModel.metadata.create_all(engine)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="InjuryGuard AI",
    description="Backend API for InjuryGuard AI hackathon prototype",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5501",
        "http://localhost:5501",

        "http://127.0.0.1:5500",
        "http://localhost:5500",

        "http://127.0.0.1:3000",
        "http://localhost:3000",

        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def on_startup():

    create_db()

    print()
    print("=" * 60)
    print("InjuryGuard AI backend started")
    print("=" * 60)
    print(f"Database : {BASE_DIR / 'injuryguard.db'}")
    print(f"Uploads  : {UPLOAD_DIR}")
    print("=" * 60)
    print()


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "project": "InjuryGuard AI",
        "status": "running",
        "message": "Backend is ready"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "backend": "InjuryGuard AI"
    }


# ============================================================
# DATE CALCULATION
# ============================================================

def calculate_days_since_injury(
    injury_date: Optional[str],
    xray_date: Optional[str]
) -> Optional[int]:

    if not injury_date or not xray_date:
        return None

    try:

        injury = date.fromisoformat(injury_date)
        xray = date.fromisoformat(xray_date)

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Dates must use YYYY-MM-DD format."
        )

    if xray < injury:

        raise HTTPException(
            status_code=400,
            detail="X-ray date cannot be earlier than injury date."
        )

    return (xray - injury).days


# ============================================================
# TIME-BASED PROTOTYPE FACTOR
# ============================================================

def calculate_time_factor(
    days_since_injury: Optional[int],
    fracture_detected: bool
) -> float:

    if not fracture_detected:
        return 1.0

    if days_since_injury is None:
        return 1.0

    if days_since_injury < 7:
        return 1.25

    elif days_since_injury < 14:
        return 1.15

    elif days_since_injury < 28:
        return 1.05

    elif days_since_injury < 42:
        return 0.95

    else:
        return 0.90


# ============================================================
# BODY RISK CALCULATION
# ============================================================

def calculate_demo_risk(
    pain_level: int,
    previous_injury: str,
    intensity: str,
    recovery_days: int,
    muscle_condition: str,
    ligament_stability: str,
    mental_readiness: str,
    sleep_quality: str,
    feedback: str,
) -> tuple[int, str]:

    # --------------------------------------------------------
    # Starting score
    # --------------------------------------------------------

    score = 10

    # --------------------------------------------------------
    # Pain
    # Maximum contribution = 30
    # --------------------------------------------------------

    pain_level = max(
        0,
        min(pain_level, 10)
    )

    score += pain_level * 3

    # --------------------------------------------------------
    # Previous injury
    # --------------------------------------------------------

    if previous_injury == "Minor previous injury":

        score += 7

    elif previous_injury == "Major previous injury":

        score += 14

    # --------------------------------------------------------
    # Training intensity
    # --------------------------------------------------------

    if intensity == "High":

        score += 8

    elif intensity == "Very High":

        score += 12

    # --------------------------------------------------------
    # Recovery
    # --------------------------------------------------------

    if recovery_days <= 1:

        score += 7

    elif recovery_days <= 3:

        score += 4

    # --------------------------------------------------------
    # Muscle condition
    # --------------------------------------------------------

    if muscle_condition == "Mild soreness":

        score += 5

    elif muscle_condition == "High fatigue":

        score += 10

    elif muscle_condition == "Cramps / severe tightness":

        score += 14

    # --------------------------------------------------------
    # Ligament stability
    # --------------------------------------------------------

    if ligament_stability == "Mild instability":

        score += 8

    elif ligament_stability == "Previous ligament issue":

        score += 10

    elif ligament_stability == "Strong instability":

        score += 17

    # --------------------------------------------------------
    # Mental readiness
    # --------------------------------------------------------

    if mental_readiness == "Worried about injury":

        score += 4

    elif mental_readiness == "High pressure / fear":

        score += 7

    # --------------------------------------------------------
    # Sleep
    # --------------------------------------------------------

    if sleep_quality == "Poor":

        score += 5

    # --------------------------------------------------------
    # Feedback
    # --------------------------------------------------------

    feedback_lower = feedback.lower()

    keywords = [
        "land",
        "jump",
        "twist",
        "unstable",
        "collapse",
        "sharp",
        "swelling",
        "giving"
    ]

    if any(
        word in feedback_lower
        for word in keywords
    ):

        score += 7

    # --------------------------------------------------------
    # Limit body score
    # --------------------------------------------------------

    score = max(
        5,
        min(score, 70)
    )

    # --------------------------------------------------------
    # Body risk level
    # --------------------------------------------------------

    if score >= 50:

        level = "High"

    elif score >= 30:

        level = "Moderate"

    else:

        level = "Low"

    return score, level


# ============================================================
# CREATE BODY ASSESSMENT
# ============================================================

@app.post("/api/assessments")
async def create_assessment(

    athlete_name: str = Form(""),
    athlete_email: str = Form(""),
    athlete_age: str = Form(""),
    athlete_gender: str = Form(""),
    athlete_blood_group: str = Form(""),
    athlete_phone: str = Form(""),

    sport: str = Form(...),
    intensity: str = Form(...),
    previous_injury: str = Form(...),
    recovery_days: int = Form(...),

    pain_location: str = Form(...),
    pain_level: int = Form(...),

    muscle_condition: str = Form(...),
    ligament_stability: str = Form(...),
    mental_readiness: str = Form(...),
    sleep_quality: str = Form(...),

    feedback: str = Form(""),

    media: Optional[UploadFile] = File(None),
):

    if not 0 <= pain_level <= 10:

        raise HTTPException(
            status_code=400,
            detail="pain_level must be between 0 and 10"
        )

    media_filename = None

    # --------------------------------------------------------
    # Optional media
    # --------------------------------------------------------

    if media and media.filename:

        allowed = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".mp4",
            ".mov",
            ".avi",
            ".mkv"
        }

        suffix = Path(
            media.filename
        ).suffix.lower()

        if suffix not in allowed:

            raise HTTPException(
                status_code=400,
                detail="Unsupported media type"
            )

        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d%H%M%S%f"
        )

        safe_name = (
            f"{timestamp}_"
            f"{Path(media.filename).name.replace(' ', '_')}"
        )

        destination = UPLOAD_DIR / safe_name

        try:

            content = await media.read()

            destination.write_bytes(content)

            media_filename = safe_name

        except Exception as e:

            raise HTTPException(
                status_code=500,
                detail=f"Could not save media: {str(e)}"
            )

    # --------------------------------------------------------
    # Calculate body risk
    # --------------------------------------------------------

    risk_score, risk_level = calculate_demo_risk(

        pain_level=pain_level,

        previous_injury=previous_injury,

        intensity=intensity,

        recovery_days=recovery_days,

        muscle_condition=muscle_condition,

        ligament_stability=ligament_stability,

        mental_readiness=mental_readiness,

        sleep_quality=sleep_quality,

        feedback=feedback
    )

    # --------------------------------------------------------
    # Database record
    # --------------------------------------------------------

    assessment = Assessment(

        athlete_name=athlete_name,
        athlete_email=athlete_email,
        athlete_age=athlete_age,
        athlete_gender=athlete_gender,
        athlete_blood_group=athlete_blood_group,
        athlete_phone=athlete_phone,

        sport=sport,

        intensity=intensity,

        previous_injury=previous_injury,

        recovery_days=recovery_days,

        injury_date=None,

        xray_date=None,

        days_since_injury=None,

        pain_location=pain_location,

        pain_level=pain_level,

        muscle_condition=muscle_condition,

        ligament_stability=ligament_stability,

        mental_readiness=mental_readiness,

        sleep_quality=sleep_quality,

        feedback=feedback,

        media_filename=media_filename,

        risk_score=risk_score,

        risk_level=risk_level
    )

    try:

        with Session(engine) as session:

            session.add(assessment)

            session.commit()

            session.refresh(assessment)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    return {

        "id": assessment.id,

        "risk_score": assessment.risk_score,

        "risk_level": assessment.risk_level,

        "media_filename": assessment.media_filename,

        "message": "Assessment saved successfully"
    }


# ============================================================
# GET ALL ASSESSMENTS
# ============================================================

@app.get("/api/assessments")
def list_assessments():

    try:

        with Session(engine) as session:

            results = session.exec(
                select(Assessment)
                .order_by(
                    Assessment.created_at.desc()
                )
            ).all()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    return [

        {
            "id": item.id,

            "athlete_name": item.athlete_name,

            "athlete_email": item.athlete_email,

            "athlete_age": item.athlete_age,

            "athlete_gender": item.athlete_gender,

            "athlete_blood_group": item.athlete_blood_group,

            "athlete_phone": item.athlete_phone,

            "sport": item.sport,

            "pain_level": item.pain_level,

            "risk_score": item.risk_score,

            "risk_level": item.risk_level,

            "injury_date": item.injury_date,

            "xray_date": item.xray_date,

            "days_since_injury": item.days_since_injury,

            "created_at": item.created_at
        }

        for item in results
    ]


# ============================================================
# X-RAY PREDICTION
# ============================================================

@app.post("/api/fracture-predict")
async def fracture_predict(

    file: UploadFile = File(...)
):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected"
        )

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }

    suffix = Path(
        file.filename
    ).suffix.lower()

    if suffix not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed"
            )
        )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%d%H%M%S%f"
    )

    original_name = Path(
        file.filename
    ).name.replace(
        " ",
        "_"
    )

    safe_name = (
        f"{timestamp}_{original_name}"
    )

    destination = UPLOAD_DIR / safe_name

    # --------------------------------------------------------
    # Save image
    # --------------------------------------------------------

    try:

        content = await file.read()

        if not content:

            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty."
            )

        destination.write_bytes(content)

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Could not save uploaded image: {str(e)}"
        )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    try:

        result = predict_fracture(
            str(destination)
        )

    except Exception as e:

        print()
        print("X-RAY PREDICTION ERROR:")
        print(str(e))
        print()

        if destination.exists():

            try:

                destination.unlink()

            except Exception:

                pass

        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )

    # --------------------------------------------------------
    # Handle predictor result
    # --------------------------------------------------------

    if isinstance(result, dict):

        prediction = result.get(
            "prediction",
            ""
        )

        confidence = result.get(
            "confidence",
            None
        )

    else:

        prediction = str(result)

        confidence = None

    prediction = prediction.upper().strip()

    # --------------------------------------------------------
    # X-ray screening risk
    # --------------------------------------------------------

    if prediction == "FRACTURED":

        risk_level = "HIGH"

        screening_message = (
            "Possible fracture-related features "
            "were detected by the screening model."
        )

    else:

        risk_level = "LOW"

        screening_message = (
            "No fracture-related features were detected "
            "by the screening model."
        )

    return {

        "prediction": prediction,

        "confidence": confidence,

        "risk_level": risk_level,

        "filename": safe_name,

        "message": screening_message,

        "disclaimer": (
            "This is an AI-assisted screening result "
            "and not a medical diagnosis."
        )
    }


# ============================================================
# COMBINED ASSESSMENT
# ============================================================

@app.post("/api/combined-assessment")
async def combined_assessment(

    # --------------------------------------------------------
    # ATHLETE INFORMATION
    # --------------------------------------------------------

    athlete_name: str = Form(""),
    athlete_email: str = Form(""),
    athlete_age: str = Form(""),
    athlete_gender: str = Form(""),
    athlete_blood_group: str = Form(""),
    athlete_phone: str = Form(""),

    # --------------------------------------------------------
    # ASSESSMENT INFORMATION
    # --------------------------------------------------------

    sport: str = Form(...),

    intensity: str = Form(...),

    previous_injury: str = Form(...),

    recovery_days: int = Form(...),

    injury_date: Optional[str] = Form(None),

    xray_date: Optional[str] = Form(None),

    pain_location: str = Form(...),

    pain_level: int = Form(...),

    muscle_condition: str = Form(...),

    ligament_stability: str = Form(...),

    mental_readiness: str = Form(...),

    sleep_quality: str = Form(...),

    feedback: str = Form(""),

    xray: Optional[UploadFile] = File(None),

    video: Optional[UploadFile] = File(None)
):

    print()
    print("=" * 60)
    print("COMBINED ASSESSMENT REQUEST")
    print("=" * 60)

    print(
        f"Athlete name: {athlete_name}"
    )

    print(
        f"Athlete email: {athlete_email}"
    )

    try:

        # ====================================================
        # 1. VALIDATE BASIC INPUT
        # ====================================================

        if not 0 <= pain_level <= 10:

            raise HTTPException(
                status_code=400,
                detail="pain_level must be between 0 and 10."
            )

        if recovery_days < 0:

            raise HTTPException(
                status_code=400,
                detail="recovery_days cannot be negative."
            )

        # ====================================================
        # 2. DATE VALIDATION
        # ====================================================

        days_since_injury = calculate_days_since_injury(
            injury_date,
            xray_date
        )

        print(
            f"Injury date: {injury_date}"
        )

        print(
            f"X-ray date: {xray_date}"
        )

        print(
            f"Days since injury: {days_since_injury}"
        )

        # ====================================================
        # 3. BODY ASSESSMENT
        # ====================================================

        body_score, body_level = calculate_demo_risk(

            pain_level=pain_level,

            previous_injury=previous_injury,

            intensity=intensity,

            recovery_days=recovery_days,

            muscle_condition=muscle_condition,

            ligament_stability=ligament_stability,

            mental_readiness=mental_readiness,

            sleep_quality=sleep_quality,

            feedback=feedback
        )

        print(
            f"Body score: {body_score}"
        )

        print(
            f"Body level: {body_level}"
        )

        # ====================================================
        # 4. INITIAL VALUES
        # ====================================================

        final_score = float(body_score)

        xray_result = None

        video_result = None

        fracture_detected = False

        xray_confidence = 0.0

        xray_contribution = 0.0

        time_factor = 1.0

        # ====================================================
        # 5. X-RAY ANALYSIS
        # ====================================================

        if xray is not None and xray.filename:

            print(
                f"X-ray received: {xray.filename}"
            )

            allowed_xray = {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            }

            xray_suffix = Path(
                xray.filename
            ).suffix.lower()

            if xray_suffix not in allowed_xray:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "X-ray must be JPG, JPEG, PNG "
                        "or WEBP."
                    )
                )

            timestamp = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d%H%M%S%f"
            )

            safe_xray_name = (
                f"xray_{timestamp}_"
                f"{Path(xray.filename).name.replace(' ', '_')}"
            )

            xray_path = UPLOAD_DIR / safe_xray_name

            # ------------------------------------------------
            # Save X-ray
            # ------------------------------------------------

            try:

                xray_content = await xray.read()

                if not xray_content:

                    raise HTTPException(
                        status_code=400,
                        detail="Uploaded X-ray file is empty."
                    )

                xray_path.write_bytes(
                    xray_content
                )

            except HTTPException:

                raise

            except Exception as e:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Could not save X-ray: {str(e)}"
                    )
                )

            print(
                f"X-ray saved: {xray_path}"
            )

            # ------------------------------------------------
            # Run X-ray model
            # ------------------------------------------------

            try:

                xray_result = predict_fracture(
                    str(xray_path)
                )

                print(
                    f"X-ray model result: {xray_result}"
                )

            except Exception as e:

                print()
                print("=" * 60)
                print("X-RAY MODEL ERROR")
                print("=" * 60)
                print(str(e))
                print("=" * 60)
                print()

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"X-ray prediction failed: {str(e)}"
                    )
                )

            # ------------------------------------------------
            # Extract prediction and confidence
            # ------------------------------------------------

            if isinstance(
                xray_result,
                dict
            ):

                xray_prediction = xray_result.get(
                    "prediction",
                    ""
                )

                try:

                    xray_confidence = float(
                        xray_result.get(
                            "confidence",
                            0
                        )
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    xray_confidence = 0.0

            else:

                xray_prediction = str(
                    xray_result
                )

                xray_confidence = 0.0

            xray_prediction = (
                xray_prediction
                .upper()
                .strip()
            )

            print(
                f"X-ray prediction: {xray_prediction}"
            )

            print(
                f"X-ray confidence: {xray_confidence}%"
            )

            # ------------------------------------------------
            # Detect fracture
            # ------------------------------------------------

            if xray_prediction == "FRACTURED":

                fracture_detected = True

                # --------------------------------------------
                # X-RAY CONTRIBUTION
                # --------------------------------------------
                #
                # Minimum contribution = 15 points
                #
                # Maximum contribution = 30 points
                #
                # Example:
                #
                # confidence = 50%
                # contribution = 22.5
                #
                # confidence = 90%
                # contribution = 28.5
                #
                # confidence = 100%
                # contribution = 30
                # --------------------------------------------

                xray_contribution = (
                    15.0
                    +
                    (
                        xray_confidence
                        * 0.15
                    )
                )

                final_score += xray_contribution

                print(
                    "FRACTURE DETECTED"
                )

                print(
                    f"X-ray contribution: "
                    f"{xray_contribution:.2f}"
                )

            else:

                fracture_detected = False

                xray_contribution = 0.0

                print(
                    "No fracture detected"
                )

                print(
                    f"X-ray confidence: "
                    f"{xray_confidence}%"
                )

                print(
                    "X-ray contribution: 0"
                )

        else:

            print(
                "No X-ray uploaded."
            )

        # ====================================================
        # 6. VIDEO ANALYSIS
        # ====================================================

        if video is not None and video.filename:

            print(
                f"Video received: {video.filename}"
            )

            allowed_video = {
                ".mp4",
                ".mov",
                ".avi",
                ".mkv"
            }

            video_suffix = Path(
                video.filename
            ).suffix.lower()

            if video_suffix not in allowed_video:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Video must be MP4, MOV, AVI "
                        "or MKV."
                    )
                )

            timestamp = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d%H%M%S%f"
            )

            safe_video_name = (
                f"video_{timestamp}_"
                f"{Path(video.filename).name.replace(' ', '_')}"
            )

            video_path = UPLOAD_DIR / safe_video_name

            # ------------------------------------------------
            # Save video
            # ------------------------------------------------

            try:

                video_content = await video.read()

                if not video_content:

                    raise HTTPException(
                        status_code=400,
                        detail="Uploaded video file is empty."
                    )

                video_path.write_bytes(
                    video_content
                )

            except HTTPException:

                raise

            except Exception as e:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Could not save video: {str(e)}"
                    )
                )

            print(
                f"Video saved: {video_path}"
            )

            # ------------------------------------------------
            # Run video model
            # ------------------------------------------------

            try:

                video_result = predict_video(
                    str(video_path)
                )

                print(
                    f"Video model result: {video_result}"
                )

            except Exception as e:

                print()
                print("=" * 60)
                print("VIDEO MODEL ERROR")
                print("=" * 60)
                print(str(e))
                print("=" * 60)
                print()

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Video analysis failed: {str(e)}"
                    )
                )

        else:

            print(
                "No video uploaded."
            )

        # ====================================================
        # 7. TIME FACTOR
        # ====================================================

        time_factor = calculate_time_factor(
            days_since_injury=days_since_injury,
            fracture_detected=fracture_detected
        )

        print(
            f"Time factor: {time_factor}"
        )

        if fracture_detected:

            final_score = (
                final_score
                *
                time_factor
            )

        # ====================================================
        # 8. LIMIT SCORE
        # ====================================================

        final_score = max(
            0,
            min(
                100,
                round(final_score)
            )
        )

        print(
            f"Final score: {final_score}"
        )

        # ====================================================
        # 9. FINAL RISK LEVEL
        # ====================================================

        if final_score >= 65:

            final_level = "HIGH"

        elif final_score >= 35:

            final_level = "MODERATE"

        else:

            final_level = "LOW"

        print(
            f"Final level: {final_level}"
        )

        # ====================================================
        # 10. MEDIA DESCRIPTION
        # ====================================================

        has_xray = (
            xray is not None
            and bool(xray.filename)
        )

        has_video = (
            video is not None
            and bool(video.filename)
        )

        if has_xray and has_video:

            media_filename = "X-ray + Video"

        elif has_xray:

            media_filename = "X-ray"

        elif has_video:

            media_filename = "Video"

        else:

            media_filename = None

        # ====================================================
        # 11. DATABASE RECORD
        # ====================================================

        assessment = Assessment(

            athlete_name=athlete_name,

            athlete_email=athlete_email,

            athlete_age=athlete_age,

            athlete_gender=athlete_gender,

            athlete_blood_group=athlete_blood_group,

            athlete_phone=athlete_phone,

            sport=sport,

            intensity=intensity,

            previous_injury=previous_injury,

            recovery_days=recovery_days,

            injury_date=injury_date,

            xray_date=xray_date,

            days_since_injury=days_since_injury,

            pain_location=pain_location,

            pain_level=pain_level,

            muscle_condition=muscle_condition,

            ligament_stability=ligament_stability,

            mental_readiness=mental_readiness,

            sleep_quality=sleep_quality,

            feedback=feedback,

            media_filename=media_filename,

            risk_score=final_score,

            risk_level=final_level
        )

        try:

            with Session(engine) as session:

                session.add(assessment)

                session.commit()

                session.refresh(assessment)

        except Exception as e:

            print()
            print("=" * 60)
            print("DATABASE ERROR")
            print("=" * 60)
            print(str(e))
            print("=" * 60)
            print()

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Database error while saving assessment: "
                    f"{str(e)}"
                )
            )

        # ====================================================
        # 12. MESSAGE
        # ====================================================

        if fracture_detected:

            message = (
                "The X-ray screening model detected "
                "fracture-related features. The X-ray "
                "screening confidence, injury assessment "
                "factors and recovery-time context were "
                "considered in the prototype risk score."
            )

        elif has_xray:

            message = (
                "The X-ray screening model did not detect "
                "fracture-related features. The remaining "
                "risk score is based on the provided "
                "assessment information."
            )

        else:

            message = (
                "Combined prototype screening result "
                "generated successfully."
            )

        # ====================================================
        # 13. SUCCESS RESPONSE
        # ====================================================

        response = {

            "success": True,

            "id": assessment.id,

            "athlete_name": athlete_name,

            "athlete_email": athlete_email,

            "athlete_age": athlete_age,

            "athlete_gender": athlete_gender,

            "athlete_blood_group": athlete_blood_group,

            "athlete_phone": athlete_phone,

            "risk_percentage": final_score,

            "risk_score": final_score,

            "risk_level": final_level,

            "message": message,

            "injury_date": injury_date,

            "xray_date": xray_date,

            "days_since_injury": days_since_injury,

            "time_factor": time_factor,

            "inputs_used": {

                "body_assessment": True,

                "xray": has_xray,

                "video": has_video,

                "injury_date": (
                    injury_date is not None
                ),

                "xray_date": (
                    xray_date is not None
                )
            },

            "xray_result": xray_result,

            "xray_confidence": xray_confidence,

            "xray_contribution": round(
                xray_contribution,
                2
            ),

            "video_result": video_result,

            "disclaimer": (
                "This is a prototype AI-assisted screening "
                "score. It is not a medical diagnosis and "
                "the percentage is not a clinically validated "
                "probability of injury."
            )
        }

        print()
        print("=" * 60)
        print("COMBINED ASSESSMENT SUCCESS")
        print("=" * 60)
        print(response)
        print("=" * 60)
        print()

        return response

    # ========================================================
    # HTTP ERROR
    # ========================================================

    except HTTPException:

        raise

    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except Exception as e:

        print()
        print("=" * 60)
        print("UNEXPECTED COMBINED ASSESSMENT ERROR")
        print("=" * 60)
        print(type(e).__name__)
        print(str(e))
        print("=" * 60)
        print()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Combined assessment failed: "
                f"{type(e).__name__}: {str(e)}"
            )
        )


# ============================================================
# ATHLETE REPORT PDF
# ============================================================

@app.get("/api/report/pdf")
def download_athlete_report():

    """
    Generate and download an Athlete Health Report PDF.
    """

    report_path = (
        BASE_DIR /
        "InjuryGuard_Athlete_Report.pdf"
    )

    try:

        # ====================================================
        # GET ASSESSMENT HISTORY
        # ====================================================

        with Session(engine) as session:

            assessments = session.exec(
                select(Assessment)
                .order_by(
                    Assessment.created_at.desc()
                )
            ).all()

        # ====================================================
        # LATEST ASSESSMENT
        # ====================================================

        latest = (
            assessments[0]
            if assessments
            else None
        )

        # ====================================================
        # ATHLETE DETAILS
        # ====================================================

        if latest:

            athlete_name = (
                latest.athlete_name
                if latest.athlete_name
                else "Not provided"
            )

            athlete_age = (
                latest.athlete_age
                if latest.athlete_age
                else "Not provided"
            )

            athlete_gender = (
                latest.athlete_gender
                if latest.athlete_gender
                else "Not provided"
            )

            athlete_blood_group = (
                latest.athlete_blood_group
                if latest.athlete_blood_group
                else "Not provided"
            )

            athlete_sport = (
                latest.sport
                if latest.sport
                else "Not provided"
            )

            athlete_email = (
                latest.athlete_email
                if latest.athlete_email
                else "Not provided"
            )

        else:

            athlete_name = "Not provided"
            athlete_age = "Not provided"
            athlete_gender = "Not provided"
            athlete_blood_group = "Not provided"
            athlete_sport = "Not provided"
            athlete_email = "Not provided"

        # ====================================================
        # PDF DOCUMENT
        # ====================================================

        document = SimpleDocTemplate(

            str(report_path),

            pagesize=A4,

            rightMargin=40,

            leftMargin=40,

            topMargin=40,

            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(

            "ReportTitle",

            parent=styles["Title"],

            alignment=TA_CENTER,

            fontSize=22,

            spaceAfter=8
        )

        subtitle_style = ParagraphStyle(

            "Subtitle",

            parent=styles["Normal"],

            alignment=TA_CENTER,

            fontSize=10,

            spaceAfter=20
        )

        heading_style = ParagraphStyle(

            "SectionHeading",

            parent=styles["Heading2"],

            fontSize=14,

            spaceBefore=15,

            spaceAfter=8
        )

        normal_style = ParagraphStyle(

            "NormalText",

            parent=styles["Normal"],

            fontSize=10,

            leading=15
        )

        small_style = ParagraphStyle(

            "SmallText",

            parent=styles["Normal"],

            fontSize=8,

            leading=11
        )

        story = []

        # ====================================================
        # TITLE
        # ====================================================

        story.append(

            Paragraph(

                "INJURYGUARD AI",

                title_style
            )
        )

        story.append(

            Paragraph(

                "ATHLETE HEALTH REPORT",

                subtitle_style
            )
        )

        story.append(

            Paragraph(

                f"Generated on: "
                f"{datetime.now().strftime('%d-%m-%Y %H:%M')}",

                small_style
            )
        )

        story.append(
            Spacer(1, 15)
        )

        # ====================================================
        # ATHLETE INFORMATION
        # ====================================================

        story.append(

            Paragraph(

                "1. Athlete Information",

                heading_style
            )
        )

        athlete_data = [

            [
                "Full Name",
                athlete_name
            ],

            [
                "Age",
                athlete_age
            ],

            [
                "Gender",
                athlete_gender
            ],

            [
                "Blood Group",
                athlete_blood_group
            ],

            [
                "Primary Sport",
                athlete_sport
            ],

            [
                "Email",
                athlete_email
            ]
        ]

        athlete_table = Table(

            athlete_data,

            colWidths=[
                150,
                350
            ]
        )

        athlete_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.lightgrey
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica"
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        story.append(
            athlete_table
        )

        # ====================================================
        # LATEST SCREENING
        # ====================================================

        story.append(

            Paragraph(

                "2. Latest Screening Result",

                heading_style
            )
        )

        if latest:

            screening_data = [

                [
                    "Risk Score",
                    f"{latest.risk_score}%"
                ],

                [
                    "Risk Level",
                    latest.risk_level
                ],

                [
                    "Sport",
                    latest.sport
                ],

                [
                    "Pain Level",
                    f"{latest.pain_level}/10"
                ],

                [
                    "Previous Injury",
                    latest.previous_injury
                ],

                [
                    "Assessment Date",
                    latest.created_at.strftime(
                        "%d-%m-%Y %H:%M"
                    )
                ]
            ]

        else:

            screening_data = [

                [
                    "Status",
                    "No assessment available"
                ]
            ]

        screening_table = Table(

            screening_data,

            colWidths=[
                150,
                350
            ]
        )

        screening_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.lightgrey
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        story.append(
            screening_table
        )

        # ====================================================
        # X-RAY HISTORY
        # ====================================================

        story.append(

            Paragraph(

                "3. X-Ray / Injury History",

                heading_style
            )
        )

        xray_rows = [

            [
                "Date",
                "Injury Date",
                "X-Ray Date",
                "Risk",
                "Level"
            ]
        ]

        for item in assessments:

            xray_rows.append([

                item.created_at.strftime(
                    "%d-%m-%Y"
                ),

                item.injury_date or "-",

                item.xray_date or "-",

                f"{item.risk_score}%",

                item.risk_level
            ])

        if len(xray_rows) == 1:

            xray_rows.append([

                "-",
                "-",
                "-",
                "-",
                "No records"
            ])

        xray_table = Table(

            xray_rows,

            colWidths=[
                85,
                90,
                90,
                70,
                75
            ],

            repeatRows=1
        )

        xray_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ])
        )

        story.append(
            xray_table
        )

        # ====================================================
        # MEDICAL HISTORY
        # ====================================================

        story.append(

            Paragraph(

                "4. Medical / Injury Details",

                heading_style
            )
        )

        medical_rows = [

            [
                "Date",
                "Pain Location",
                "Pain",
                "Muscle",
                "Ligament"
            ]
        ]

        for item in assessments:

            medical_rows.append([

                item.created_at.strftime(
                    "%d-%m-%Y"
                ),

                item.pain_location,

                f"{item.pain_level}/10",

                item.muscle_condition,

                item.ligament_stability
            ])

        if len(medical_rows) == 1:

            medical_rows.append([

                "-",
                "No records",
                "-",
                "-",
                "-"
            ])

        medical_table = Table(

            medical_rows,

            colWidths=[
                75,
                105,
                55,
                115,
                100
            ],

            repeatRows=1
        )

        medical_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ])
        )

        story.append(
            medical_table
        )

        # ====================================================
        # ASSESSMENT HISTORY
        # ====================================================

        story.append(

            Paragraph(

                "5. Assessment History",

                heading_style
            )
        )

        assessment_rows = [

            [
                "Date",
                "Sport",
                "Pain",
                "Risk",
                "Level"
            ]
        ]

        for item in assessments:

            assessment_rows.append([

                item.created_at.strftime(
                    "%d-%m-%Y"
                ),

                item.sport,

                f"{item.pain_level}/10",

                f"{item.risk_score}%",

                item.risk_level
            ])

        if len(assessment_rows) == 1:

            assessment_rows.append([

                "-",
                "-",
                "-",
                "-",
                "No records"
            ])

        assessment_table = Table(

            assessment_rows,

            colWidths=[
                90,
                100,
                70,
                80,
                90
            ],

            repeatRows=1
        )

        assessment_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ])
        )

        story.append(
            assessment_table
        )

        # ====================================================
        # DISCLAIMER
        # ====================================================

        story.append(
            Spacer(1, 20)
        )

        story.append(

            Paragraph(

                "<b>Important Disclaimer</b>",

                heading_style
            )
        )

        story.append(

            Paragraph(

                "This report is generated by InjuryGuard AI "
                "for AI-assisted sports injury screening. "
                "The results are not a medical diagnosis and "
                "should not replace evaluation by a qualified "
                "healthcare professional.",

                normal_style
            )
        )

        # ====================================================
        # BUILD PDF
        # ====================================================

        document.build(
            story
        )

        # ====================================================
        # RETURN DOWNLOAD
        # ====================================================

        return FileResponse(

            path=str(report_path),

            media_type="application/pdf",

            filename="InjuryGuard_Athlete_Report.pdf"
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("REPORT PDF ERROR")
        print("=" * 60)
        print(str(e))
        print("=" * 60)
        print()

        raise HTTPException(

            status_code=500,

            detail=(
                f"Could not generate athlete report: "
                f"{str(e)}"
            )
        )