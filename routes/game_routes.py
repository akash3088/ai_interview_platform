from flask import Blueprint, render_template, request, session, redirect
from data.questions import QUESTIONS
from data.rewards import XP_REWARDS, XP_TO_POINT
import random

game_bp = Blueprint("game", __name__)

# -----------------------------
# BOSS SETTINGS
# -----------------------------
BOSS_HP = {
    "easy": 50,
    "medium": 100,
    "hard": 150
}

# Keeping this block is fine if you want it for future balancing/reference
BOSS_DAMAGE = {
    "correct": 0,
    "partial": 5,
    "wrong": 15
}


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_boss_damage(result, stage, difficulty, defense):
    base_damage = {
        "correct": 0,
        "partial": 5,
        "wrong": 15
    }

    difficulty_bonus = {
        "easy": 0,
        "medium": 4,
        "hard": 8
    }

    raw_damage = base_damage[result] + ((stage - 1) * 3) + difficulty_bonus[difficulty]

    if result == "correct":
        return 0

    return max(2, raw_damage - defense)


def get_game_progress_key():
    user_id = session.get("user_id")
    return f"progress_user_{user_id}"


def get_player_stats_key():
    user_id = session.get("user_id")
    return f"player_stats_user_{user_id}"


def get_upgrade_cost(level):
    costs = [1, 2, 4, 8, 12, 16, 20]

    if level < len(costs):
        return costs[level]

    return costs[-1] + ((level - len(costs) + 1) * 4)


def initialize_progress():
    progress_key = get_game_progress_key()
    stats_key = get_player_stats_key()

    if progress_key not in session:
        session[progress_key] = {
            "stage1_easy": True,
            "stage1_medium": False,
            "stage1_hard": False,

            "stage2_easy": False,
            "stage2_medium": False,
            "stage2_hard": False,

            "stage3_easy": False,
            "stage3_medium": False,
            "stage3_hard": False,

            "stage4_easy": False,
            "stage4_medium": False,
            "stage4_hard": False,

            "stage5_easy": False,
            "stage5_medium": False,
            "stage5_hard": False
        }

    if stats_key not in session:
        session[stats_key] = {
            "xp": 0,
            "points": 0,

            "attack": 30,
            "xp_bonus": 0,
            "defense": 0,

            "attack_level": 0,
            "xp_bonus_level": 0,
            "defense_level": 0
        }
    else:
        player = session[stats_key]

        if "xp" not in player:
            player["xp"] = 0
        if "points" not in player:
            player["points"] = 0
        if "attack" not in player:
            player["attack"] = 30
        if "xp_bonus" not in player:
            player["xp_bonus"] = 0
        if "defense" not in player:
            player["defense"] = 0

        if "attack_level" not in player:
            player["attack_level"] = 0
        if "xp_bonus_level" not in player:
            player["xp_bonus_level"] = 0
        if "defense_level" not in player:
            player["defense_level"] = 0

        session[stats_key] = player


def load_battle_questions(role, stage, difficulty):
    question_pool = QUESTIONS[role][stage][difficulty]
    selected_questions = random.sample(question_pool, min(5, len(question_pool)))
    return selected_questions


def evaluate_answer(user_answer, keywords):
    user_answer = user_answer.lower()
    score = 0

    for word in keywords:
        if word in user_answer:
            score += 1

    if score >= 2:
        return "correct"
    elif score == 1:
        return "partial"
    else:
        return "wrong"


# -----------------------------
# ROUTES
# -----------------------------
@game_bp.route("/game_dashboard")
def game_dashboard():
    role = request.args.get("role")

    initialize_progress()

    progress = session[get_game_progress_key()]
    player = session[get_player_stats_key()]

    attack_cost = get_upgrade_cost(player["attack_level"])
    xp_bonus_cost = get_upgrade_cost(player["xp_bonus_level"])
    defense_cost = get_upgrade_cost(player["defense_level"])

    return render_template(
        "game_dashboard.html",
        role=role,
        progress=progress,
        player=player,
        attack_cost=attack_cost,
        xp_bonus_cost=xp_bonus_cost,
        defense_cost=defense_cost
    )


@game_bp.route("/upgrade/<upgrade_type>")
def upgrade_stat(upgrade_type):
    role = request.args.get("role")

    initialize_progress()

    stats_key = get_player_stats_key()
    player = session[stats_key]

    if upgrade_type == "attack":
        cost = get_upgrade_cost(player["attack_level"])

        if player["points"] >= cost:
            player["points"] -= cost
            player["attack"] += 5
            player["attack_level"] += 1

    elif upgrade_type == "xp_bonus":
        cost = get_upgrade_cost(player["xp_bonus_level"])

        if player["points"] >= cost:
            player["points"] -= cost
            player["xp_bonus"] += 10
            player["xp_bonus_level"] += 1

    elif upgrade_type == "defense":
        cost = get_upgrade_cost(player["defense_level"])

        if player["points"] >= cost:
            player["points"] -= cost
            player["defense"] += 2
            player["defense_level"] += 1

    session[stats_key] = player

    return redirect(f"/game_dashboard?role={role}")


@game_bp.route("/game")
def game():
    initialize_progress()

    role = request.args.get("role")
    stage = int(request.args.get("stage"))
    difficulty = request.args.get("difficulty")

    questions = load_battle_questions(role, stage, difficulty)

    boss_hp = BOSS_HP[difficulty] + (stage - 1) * 20
    user_hp = 100

    session["battle"] = {
        "questions": questions,
        "current_q": 0,
        "boss_hp": boss_hp,
        "boss_max_hp": boss_hp,
        "user_hp": user_hp,
        "user_max_hp": user_hp,
        "stage": stage,
        "difficulty": difficulty,
        "role": role
    }

    first_question = questions[0]["q"]

    return render_template(
        "game.html",
        role=role,
        stage=stage,
        difficulty=difficulty,
        question=first_question,
        boss_hp=boss_hp,
        boss_max_hp=boss_hp,
        user_hp=user_hp,
        user_max_hp=user_hp
    )


@game_bp.route("/submit_answer", methods=["POST"])
def submit_answer():
    user_answer = request.form["answer"]

    battle = session["battle"]

    role = battle["role"]
    stage = battle["stage"]
    difficulty = battle["difficulty"]

    q_index = battle["current_q"]
    question_data = battle["questions"][q_index]

    result = evaluate_answer(user_answer, question_data["keywords"])

    stats_key = get_player_stats_key()
    progress_key = get_game_progress_key()

    player = session[stats_key]
    progress = session[progress_key]

    # Track damage dealt to boss
    damage_to_boss = 0

    if result == "correct":
        damage_to_boss = player["attack"]
        battle["boss_hp"] -= damage_to_boss

    elif result == "partial":
        damage_to_boss = int(player["attack"] * 0.5)
        battle["boss_hp"] -= damage_to_boss

    # Track damage received from boss
    damage_to_user = get_boss_damage(result, stage, difficulty, player["defense"])
    battle["user_hp"] -= damage_to_user

    battle["current_q"] += 1
    session["battle"] = battle

    # -----------------------------
    # WIN
    # -----------------------------
    if battle["boss_hp"] <= 0:
        base_xp = XP_REWARDS[stage][difficulty]

        key = f"stage{stage}_{difficulty}"
        already_cleared = progress.get(key + "_cleared", False)

        if already_cleared:
            base_xp = int(base_xp * 0.3)

        reward_xp = base_xp + player["xp_bonus"]
        player["xp"] += reward_xp

        # Mark cleared for anti-farming
        progress[key + "_cleared"] = True

        # Convert XP to points
        next_point = player["points"] + 1
        required_xp = XP_TO_POINT.get(next_point, 999999)

        while player["xp"] >= required_xp:
            player["points"] += 1
            player["xp"] -= required_xp

            next_point = player["points"] + 1
            required_xp = XP_TO_POINT.get(next_point, 999999)

        # Unlock progression
        if stage == 1 and difficulty == "easy":
            progress["stage1_medium"] = True

        elif stage == 1 and difficulty == "medium":
            progress["stage1_hard"] = True

        elif stage == 1 and difficulty == "hard":
            progress["stage2_easy"] = True

        elif stage == 2 and difficulty == "easy":
            progress["stage2_medium"] = True

        elif stage == 2 and difficulty == "medium":
            progress["stage2_hard"] = True

        elif stage == 2 and difficulty == "hard":
            progress["stage3_easy"] = True

        elif stage == 3 and difficulty == "easy":
            progress["stage3_medium"] = True

        elif stage == 3 and difficulty == "medium":
            progress["stage3_hard"] = True

        elif stage == 3 and difficulty == "hard":
            progress["stage4_easy"] = True

        elif stage == 4 and difficulty == "easy":
            progress["stage4_medium"] = True

        elif stage == 4 and difficulty == "medium":
            progress["stage4_hard"] = True

        elif stage == 4 and difficulty == "hard":
            progress["stage5_easy"] = True

        elif stage == 5 and difficulty == "easy":
            progress["stage5_medium"] = True

        elif stage == 5 and difficulty == "medium":
            progress["stage5_hard"] = True

        session[stats_key] = player
        session[progress_key] = progress

        print(session[progress_key])

        return render_template(
            "game.html",
            role=role,
            stage=stage,
            difficulty=difficulty,
            boss_hp=max(battle["boss_hp"], 0),
            boss_max_hp=battle["boss_max_hp"],
            user_hp=battle["user_hp"],
            user_max_hp=battle["user_max_hp"],
            message=f"🏆 Boss Defeated! +{reward_xp} XP",
            result=result,
            damage_to_boss=damage_to_boss,
            damage_to_user=damage_to_user,
            defense=player["defense"]
        )

    # -----------------------------
    # LOSE
    # -----------------------------
    if battle["user_hp"] <= 0:
        return render_template(
            "game.html",
            role=role,
            stage=stage,
            difficulty=difficulty,
            boss_hp=battle["boss_hp"],
            boss_max_hp=battle["boss_max_hp"],
            user_hp=max(battle["user_hp"], 0),
            user_max_hp=battle["user_max_hp"],
            message="💀 You Were Defeated!",
            result=result,
            damage_to_boss=damage_to_boss,
            damage_to_user=damage_to_user,
            defense=player["defense"]
        )

    # -----------------------------
    # FAILED AFTER 5 QUESTIONS
    # -----------------------------
    if battle["current_q"] >= 5:
        return render_template(
            "game.html",
            role=role,
            stage=stage,
            difficulty=difficulty,
            boss_hp=battle["boss_hp"],
            boss_max_hp=battle["boss_max_hp"],
            user_hp=battle["user_hp"],
            user_max_hp=battle["user_max_hp"],
            message="⚔ Battle Failed!",
            result=result,
            damage_to_boss=damage_to_boss,
            damage_to_user=damage_to_user,
            defense=player["defense"]
        )

    next_question = battle["questions"][battle["current_q"]]["q"]

    return render_template(
        "game.html",
        role=role,
        stage=stage,
        difficulty=difficulty,
        question=next_question,
        boss_hp=battle["boss_hp"],
        boss_max_hp=battle["boss_max_hp"],
        user_hp=battle["user_hp"],
        user_max_hp=battle["user_max_hp"],
        result=result,
        damage_to_boss=damage_to_boss,
        damage_to_user=damage_to_user,
        defense=player["defense"]
    )