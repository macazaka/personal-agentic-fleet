r"""
Exercise, Traditional Strength Training, and Video Management for Personal Agentic Fleet.
Manages FFD exercise videos at Z:\Career - Body Building\FFD and Akhada Strength Training with
Mudgal (Karlakattai), Samtola, and Bhim Gadha across a 6-day weekly split (Sunday as Rest).
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import os
from fleet.config import load_fleet_config

_fleet_cfg = load_fleet_config()
_custom_videos_dir = _fleet_cfg.get("agents", {}).get("health", {}).get("videos_directory") or os.getenv("FLEET_VIDEOS_DIR")
if _custom_videos_dir and Path(_custom_videos_dir).exists():
    FFD_VIDEOS_DIR = Path(_custom_videos_dir)
else:
    FFD_VIDEOS_DIR = Path(r"Z:\Career - Body Building\FFD")


def get_video_type_and_category(filename: str) -> Tuple[str, str]:
    """
    Classifies a video into high-level type ('exercise' or 'diet')
    and a specific sub-category.
    """
    name_lower = filename.lower()

    # 1. Diet, Nutrition & Smoothies
    if any(k in name_lower for k in ["smoothie", "tea", "coffee", "vitamin"]):
        video_type = "diet"
        if "smoothie" in name_lower:
            cat = "Smoothies & Green Drinks"
        elif "vitamin" in name_lower:
            cat = "Vitamins & Micronutrients"
        elif "tea" in name_lower or "coffee" in name_lower:
            cat = "Tea, Coffee & Beverages"
        else:
            cat = "Diet & Nutrition"
        return video_type, cat

    # 2. Exercise, Mobility & Akhada Conditioning
    video_type = "exercise"
    if "anti gravity" in name_lower:
        cat = "Anti-Gravity & Glucose Drop"
    elif "walking" in name_lower:
        cat = "Weighted Walking & Aerobic"
    elif "nitric oxide" in name_lower:
        cat = "Nitric Oxide Dump (NOD)"
    elif any(k in name_lower for k in ["warm up", "warm-up", "warmed up"]):
        cat = "World's Best Warm-Up & Mobility"
    elif "surya namaskar" in name_lower:
        cat = "Surya Namaskar Series"
    elif "desk" in name_lower or "chair" in name_lower:
        cat = "Desk & Office Conditioning"
    elif "yoga" in name_lower:
        cat = "Super Brain Yoga & Flexibility"
    elif "strength" in name_lower:
        cat = "Upper Body & Strength"
    else:
        cat = "Exercise & Conditioning"

    return video_type, cat


def list_exercise_videos(video_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    r"""
    Lists all MP4 videos available in Z:\Career - Body Building\FFD.
    Separates exercise videos from diet/nutrition videos.
    """
    if not FFD_VIDEOS_DIR.exists():
        return []

    videos = []
    for f in sorted(FFD_VIDEOS_DIR.glob("*.mp4")):
        clean_name = re.sub(r"^\d+\s*-\s*", "", f.stem)
        clean_name = clean_name.replace("_", " ").strip()
        size_mb = round(f.stat().st_size / (1024 * 1024), 1)
        v_type, category = get_video_type_and_category(f.name)

        if video_type_filter and v_type != video_type_filter.lower():
            continue

        videos.append({
            "id": re.sub(r"[^a-zA-Z0-9_-]", "_", f.stem),
            "filename": f.name,
            "title": clean_name,
            "video_type": v_type,
            "category": category,
            "size_mb": size_mb,
            "file_path": str(f)
        })

    return videos


def get_strength_training_plan() -> Dict[str, Any]:
    """
    Returns the 6-day weekly training regimen with Sunday as Rest:
    - Monday: Mudgal (Karlakattai)
    - Tuesday: Active FFD Reversal (Mandatory World's Best Warm-up, Surya Namaskar, Super Brain Yoga)
    - Wednesday: Samtola (Wooden Barbell)
    - Thursday: Active FFD Reversal (Mandatory World's Best Warm-up, NOD, Weighted Walking)
    - Friday: Bhim Gadha (Traditional Mace)
    - Saturday: Akhada Flow Integration (Mandatory World's Best Warm-up, Triple Tool Flow, Desk Yoga)
    - Sunday: Rest & Regeneration
    """
    return {
        "schedule": "6 Days a Week (Monday to Saturday, Sunday Rest)",
        "rest_day": "Sunday",
        "philosophy": "Traditional Indian Akhada Conditioning (Mudgal, Samtola, Bhim Gadha) + Daily Mandatory FFD Reversal Protocols (World's Best Warm-Up, Antigravity Step Climbing, Nitric Oxide Dump, Surya Namaskar, Super Brain Yoga)",
        "equipment": [
            {
                "name": "Mudgal (Karlakattai / Indian Clubbell)",
                "description": "Handcrafted wooden club. Builds rotational shoulder mobility, bulletproof rotator cuffs, forearm torque, and tendon resilience.",
                "primary_movements": "Akal (Outward swing), Bikal (Inward swing), Dasti (Alternating clean & swing), Chest Mills"
            },
            {
                "name": "Samtola (Traditional Wooden Barbell / Log)",
                "description": "Heavy cylindrical wooden barbell. Builds foundational pushing, pulling, and leg strength with authentic thick-grip stimulation.",
                "primary_movements": "Shoulder Overhead Press, Bicep Curls, Bent-Over Rows, Squats, Good Mornings"
            },
            {
                "name": "Bhim Gadha (Traditional Indian Mace)",
                "description": "Leveraged long-handle heavy mace. Develops 360-degree rotational strength, bulletproof core anti-rotation, lat expansion, and hip drive.",
                "primary_movements": "360 Swings (Left & Right), 10-to-2s, Pendulum Swings, Gada Squats, Barbarian Squats"
            }
        ],
        "mandatory_daily_items": [
            "World's Best Warm-Up (Dr. Pramod Tripathi, 5-10 mins) before every physical session",
            "Antigravity Step Climbing (8-10 stairs repeatedly for 5-7 mins) 1 hour 45 minutes after each meal",
            "Super Brain Yoga (14-21 reps with tongue to roof of mouth) for neural alertness",
            "Proper hydration (Shahi Pani / 3-4 liters daily)"
        ],
        "days": [
            {
                "day_number": 1,
                "day_name": "Monday",
                "tool": "Mudgal",
                "title": "Mudgal (Karlakattai) Armor & Rotational Mobility",
                "focus": "Rotator Cuff Fortification, Grip Strength, Forearm Torque & Thoracic Mobility",
                "primary_tool": "Mudgal (Karlakattai)",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 5-7 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up (Full spinal & joint prep)", "sets_reps": "5-7 mins"},
                    {"exercise": "Mudgal: Basic Akal (Outward swings)", "sets_reps": "3 sets x 10 reps each arm"},
                    {"exercise": "Mudgal: Basic Bikal (Inward swings)", "sets_reps": "3 sets x 10 reps each arm"},
                    {"exercise": "Mudgal: Dasti (Alternating clean & flow swing)", "sets_reps": "3 sets x 12 reps"},
                    {"exercise": "Mudgal: Chest Mills & Wrist Rotations", "sets_reps": "3 sets x 10 reps"},
                    {"exercise": "Mudgal: Overhead Locked Farmer Walk", "sets_reps": "2 rounds x 40 paces"},
                    {"exercise": "FFD Post-Meal Protocol: Antigravity Step Climbing (8-10 stairs repeatedly)", "sets_reps": "5-7 mins (1h45m after meals)"},
                    {"exercise": "Cooldown: Lat stretching, forearm flexion/extension & deep breathing", "sets_reps": "3-5 mins"}
                ]
            },
            {
                "day_number": 2,
                "day_name": "Tuesday",
                "tool": "FFD Protocol",
                "title": "Active FFD Reversal & Cardiovascular Flow",
                "focus": "Aerobic Glucose Siphon, Spine Flexibility, Brain Oxygenation & NOD Circulation",
                "primary_tool": "FFD Bodyweight & Mobility",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 10 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up (Complete 10-min sequence)", "sets_reps": "10 mins (Mandatory)"},
                    {"exercise": "FFD Protocol: 12 Rounds Surya Namaskar with synchronized breathwork", "sets_reps": "12 continuous cycles"},
                    {"exercise": "FFD Protocol: Super Brain Yoga (Earlobes crossed, squats on toes, tongue on roof)", "sets_reps": "14-21 reps (morning)"},
                    {"exercise": "FFD Protocol: Desk / Chair Surya Namaskar (Mid-day posture reset)", "sets_reps": "5-10 mins at desk"},
                    {"exercise": "FFD Protocol: Antigravity Step Climbing (1h45m after lunch & dinner)", "sets_reps": "5-7 mins (8-10 steps)"},
                    {"exercise": "Alternative: Nitric Oxide Dump (4 rapid movements: Squats, Arm raises, Jacks, Punches)", "sets_reps": "3 rounds x 2 mins"},
                    {"exercise": "Cooldown: Shavasana, hamstring decompression & diaphragm breathing", "sets_reps": "5 mins"}
                ]
            },
            {
                "day_number": 3,
                "day_name": "Wednesday",
                "tool": "Samtola",
                "title": "Samtola (Wooden Barbell) Compound Power",
                "focus": "Thick-Grip Pulling, Overhead Pushing, Posture Alignment & Posterior Chain Strength",
                "primary_tool": "Samtola (Wooden Barbell)",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 5-7 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up & Shoulder Dislocations", "sets_reps": "5-7 mins"},
                    {"exercise": "Samtola: Overhead Military Shoulder Press (Strict form)", "sets_reps": "3 sets x 10-12 reps"},
                    {"exercise": "Samtola: Thick-Grip Bent-Over Rows", "sets_reps": "3 sets x 10-12 reps"},
                    {"exercise": "Samtola: Front / Zercher Squats with wooden log", "sets_reps": "3 sets x 10 reps"},
                    {"exercise": "Samtola: Strict Standing Bicep Curls to Chest", "sets_reps": "3 sets x 10-12 reps"},
                    {"exercise": "Samtola: Stiff-Leg Deadlifts / Good Mornings", "sets_reps": "3 sets x 10 reps"},
                    {"exercise": "FFD Post-Meal Protocol: Antigravity Step Climbing (8-10 stairs repeatedly)", "sets_reps": "5-7 mins (1h45m after meals)"},
                    {"exercise": "Cooldown: Chest doorway stretch, hamstring relief & deep belly breathing", "sets_reps": "3-5 mins"}
                ]
            },
            {
                "day_number": 4,
                "day_name": "Thursday",
                "tool": "FFD Protocol",
                "title": "Active FFD Conditioning & Weighted Walking",
                "focus": "Mitochondrial Density, Vasodilation, Joint Decompression & Glucose Burning",
                "primary_tool": "Weighted Vest / Ruck & FFD Protocols",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 10 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up (10 mins)", "sets_reps": "10 mins (Mandatory)"},
                    {"exercise": "FFD Nitric Oxide Dump (NOD): 3 rounds of 4 exercises for rapid nitric oxide surge", "sets_reps": "3 rounds (takes 2 mins)"},
                    {"exercise": "FFD Weighted Walking: Brisk outdoor walking with weight vest or light backpack", "sets_reps": "35-45 mins continuous"},
                    {"exercise": "FFD Super Brain Yoga (14-21 squats) for mental alertness and focus", "sets_reps": "2 rounds x 14 reps"},
                    {"exercise": "FFD Post-Meal Protocol: Antigravity Step Climbing (1h45m after meals)", "sets_reps": "5-7 mins"},
                    {"exercise": "Cooldown: Hip flexor lunges, calf stretches & Anulom Vilom breathing", "sets_reps": "5 mins"}
                ]
            },
            {
                "day_number": 5,
                "day_name": "Friday",
                "tool": "Bhim Gadha",
                "title": "Bhim Gadha (Mace) Core Torque & Rotational Power",
                "focus": "360 Rotational Dynamics, Anti-Rotation Core Stability, Lat Flare & Hip Snap",
                "primary_tool": "Bhim Gadha (Indian Mace)",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 5-7 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up & Arm Swings", "sets_reps": "5-7 mins"},
                    {"exercise": "Bhim Gadha: Front & Back Pendulum Swings (Pendulum warm-up)", "sets_reps": "3 sets x 15 reps"},
                    {"exercise": "Bhim Gadha: Beginner 360 Swings (Right & Left side alternating)", "sets_reps": "3 sets x 10 reps/side"},
                    {"exercise": "Bhim Gadha: 10-to-2 Heavy Rotational Swings", "sets_reps": "3 sets x 8-10 reps/side"},
                    {"exercise": "Bhim Gadha: Gada Front Squats (Heavy head rested in rack position)", "sets_reps": "3 sets x 10 reps"},
                    {"exercise": "Bhim Gadha: Barbarian Squats (Squat down -> 360 pull over)", "sets_reps": "3 sets x 8 reps"},
                    {"exercise": "FFD Post-Meal Protocol: Antigravity Step Climbing (8-10 stairs repeatedly)", "sets_reps": "5-7 mins (1h45m after meals)"},
                    {"exercise": "Cooldown: Lat elongation on doorway / bar, spinal twist & deep breathing", "sets_reps": "4 mins"}
                ]
            },
            {
                "day_number": 6,
                "day_name": "Saturday",
                "tool": "Akhada Flow",
                "title": "Akhada Flow Integration & Full Functional Reversal",
                "focus": "Full Body Coordination, Joint Flossing, Fascial Elasticity & Deep Metabolic Activation",
                "primary_tool": "Triple Tool Integration (Mudgal + Samtola + Bhim Gadha)",
                "mandatory_warmup": "World's Best Warm-up (Dr. Pramod Tripathi, 10 mins)",
                "routine": [
                    {"exercise": "Mandatory Warm-up: World's Best Warm-up (Complete 10-min sequence)", "sets_reps": "10 mins (Mandatory)"},
                    {"exercise": "Triple Tool Flow: Mudgal Akal (10) -> Samtola Squat-Press (8) -> Bhim Gadha 360s (10)", "sets_reps": "3 full rounds with 90s rest"},
                    {"exercise": "FFD Surya Namaskar: 6-8 meditative rounds with focus on breath control", "sets_reps": "6-8 rounds"},
                    {"exercise": "FFD Desk / Office Stretching: Hip & thoracic mobility sequence", "sets_reps": "5-7 mins"},
                    {"exercise": "FFD Post-Meal Protocol: Antigravity Step Climbing (1h45m after meals)", "sets_reps": "5-7 mins"},
                    {"exercise": "Cooldown: Full-body yoga nidra / deep relaxation & Shavasana", "sets_reps": "8-10 mins"}
                ]
            },
            {
                "day_number": 7,
                "day_name": "Sunday",
                "tool": "Rest",
                "title": "Complete Rest, Recovery & Rejuvenation",
                "focus": "Musculoskeletal Cellular Repair, Glycogen Replenishment & Autonomic Nervous System Reset",
                "primary_tool": "Active Recovery & Hydration",
                "mandatory_warmup": "Gentle morning joint rotation & light breathing",
                "routine": [
                    {"exercise": "Full Rest from Weight Lifting & Heavy Step Climbing", "sets_reps": "All Day (Mandatory Rest)"},
                    {"exercise": "Hydration: Shahi Pani (1L water + sabja/chia + saffron + lemon + rock salt)", "sets_reps": "Sip throughout morning"},
                    {"exercise": "Mindful Nutrition: Strictly adhere to 25-25-50% plate rule (Salad, Sprouts/Veg, Dal, Khapli)", "sets_reps": "Breakfast, Lunch, Dinner"},
                    {"exercise": "Leisurely Walk: 20-30 mins relaxed walking in nature or park (non-strenuous)", "sets_reps": "Optional / Gentle"},
                    {"exercise": "Pranayama / Breathwork: Anulom Vilom & Bhramari for nervous system calm", "sets_reps": "10-15 mins"},
                    {"exercise": "Sleep Hygiene: Ensure 7-8 hours deep sound sleep; lights out by 10:30 PM", "sets_reps": "Essential"}
                ]
            }
        ],
        "youtube_playlists": [
            {
                "title": "Mudgal Beginner Practice Playlists",
                "search_url": "https://www.youtube.com/results?search_query=mudgal+workout+for+beginners+playlist",
                "tag": "Mudgal / Karlakattai"
            },
            {
                "title": "Samtola Traditional Barbell Playlists",
                "search_url": "https://www.youtube.com/results?search_query=samtola+exercise+beginner+playlist",
                "tag": "Samtola"
            },
            {
                "title": "Bhim Gadha 360 Swings Beginner Technique",
                "search_url": "https://www.youtube.com/results?search_query=bhim+gadha+workout+beginner+playlist",
                "tag": "Bhim Gadha / Mace"
            },
            {
                "title": "My YouTube Playlists ('Beginner')",
                "search_url": "https://www.youtube.com/feed/library",
                "tag": "My Playlists"
            }
        ]
    }


def get_ffd_exercise_protocol() -> Dict[str, Any]:
    """Returns the Freedom From Diabetes specific exercise protocol."""
    return {
        "non_negotiables": [
            "Start Morning Smoothie (250ml)",
            "Stop All Dairy Products (Cow/Buffalo milk, curd, paneer, butter, ghee)",
            "Do Anti-gravity Exercises (1h 45m post-meal)"
        ],
        "mandatory_warmup": {
            "name": "World's Best Warm-Up by Dr. Pramod Tripathi",
            "frequency": "Mandatory every day before any workout or morning activity",
            "duration": "5 to 10 minutes",
            "purpose": "Full-body joint mobilization, synovial fluid activation, and core body temperature elevation to prevent DOMS and injury."
        },
        "antigravity_step_climbing": {
            "timing": "Exactly 1 hour and 45 minutes after starting each meal (Breakfast, Lunch, Dinner)",
            "protocol": "Climb up and down 8 to 10 stairs repeatedly for 5 to 7 minutes until you feel breathless.",
            "rules": "Do not climb continuously on multiple floors. Rest 5 min until breath is normal, drink a glass of water, dry hands, and check BSL.",
            "biological_mechanism": "Triggers insulin-independent GLUT-4 translocation in quadriceps, glutes, and calves, clearing post-meal blood glucose directly into muscle glycogen stores!"
        },
        "nitric_oxide_dump": {
            "alternative": "Ideal alternative if step climbing is not possible or for joint comfort.",
            "movements": "4 rapid full-body movements (Squats, Arm raises, Non-jumping jacks, Shoulder punches).",
            "video_url": "https://youtu.be/QOrBraz2Lr0?si=qZfYqt2Ucox-z3CL",
            "local_video": "04 - Modified Nitric Oxide Dump Exercise for Diabetes.mp4"
        },
        "hypoglycemia_protocol": {
            "warning": "FFD diet and exercise may drop Blood Sugar Level (BSL) quickly.",
            "steps": [
                {"bsl_range": "80 - 100 mg/dL", "action": "Have 1 date/khajoor + 1 tbsp fresh coconut + 1 glass water."},
                {"bsl_range": "70 - 80 mg/dL", "action": "Have 2 dates + 1 tbsp fresh coconut (or 2 almonds) + 1 glass water."},
                {"bsl_range": "< 70 mg/dL", "action": "Have 3 tsp sugar OR 3 dates immediately + 1 glass water."},
                {"safety_note": "Recheck BSL every 20 minutes until stabilized. Contact doctor if BSL does not rise after 3 attempts."}
            ]
        }
    }
