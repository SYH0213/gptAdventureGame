import os
import json
import re # 정규 표현식 모듈 추가
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

app = Flask(__name__)

# Google Gemini API 키 설정
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# 게임 상태를 저장할 변수
game_history = []
player_state = {
    "location": "어두운 동굴 입구",
    "health": 100,
    "max_health": 100,
    "attack": 10,
    "defense": 5,
    "level": 1,
    "experience": 0,
    "inventory": [],
    "status_effects": [],
    "quest_progress": {},
    "current_goal": "" # 현재 게임의 목표를 저장할 필드 추가
}

# 게임 단계 관리 변수: "story_selection", "playing", "game_over"
game_phase = "story_selection"
# 선택된 스토리의 초기 프롬프트 내용을 저장할 변수
selected_story_initial_prompt = ""

# Gemini 모델 초기화
model = genai.GenerativeModel('gemini-2.5-flash') # 모델 이름을 'gemini-2.5-flash'로 유지

# 프롬프트에 포함할 최근 대화 턴 수 제한
MAX_HISTORY_TURNS = 5 # 최근 5턴 (사용자 입력 + 모델 응답)을 포함

# game_rules.md 파일에서 규칙을 읽어오는 함수
def get_game_rules():
    try:
        with open("game_rules2.md", "r", encoding="utf-8") as f: # 파일 이름을 game_rules2.md로 변경
            return f.read()
    except FileNotFoundError:
        return ""

@app.route('/')
def index():
    """메인 웹 인터페이스를 렌더링합니다."""
    return render_template('index.html')

@app.route('/select_story', methods=['POST'])
def select_story():
    """플레이어가 입력한 스토리를 설정하고 게임을 시작합니다."""
    global game_phase
    global selected_story_initial_prompt
    global game_history
    global player_state

    if game_phase != "story_selection":
        return jsonify({"error": "Game is already in progress or not in story selection phase."}), 400

    user_story_description = request.json.get('user_story_description')
    if not user_story_description:
        return jsonify({"error": "User story description is required."}), 400

    # 사용자 입력 스토리를 기반으로 초기 프롬프트 설정
    selected_story_initial_prompt = f"당신은 인터랙티브 텍스트 어드벤처 게임의 게임 마스터입니다. 플레이어는 다음 스토리로 게임을 시작하고 싶어합니다: '{user_story_description}'. 이 스토리를 바탕으로 게임을 진행해주세요. 답변은 200자 이내로 간결하게 작성하고, 다음 행동에 대한 몇 가지 선택지를 제시해주세요. 하지만 플레이어는 제시된 선택지 외에도 자유롭게 행동을 입력할 수 있습니다. 게임의 시작은 이 스토리의 첫 상황 서술입니다."

    # 게임 상태 초기화 및 게임 단계 변경
    game_history = []
    player_state = {
        "location": "어두운 동굴 입구",
        "health": 100,
        "max_health": 100,
        "attack": 10,
        "defense": 5,
        "level": 1,
        "experience": 0,
        "inventory": [],
        "status_effects": [],
        "quest_progress": {},
        "current_goal": "" # 초기화 시 목표도 초기화
    }
    game_phase = "playing"

    # 게임 시작 메시지를 Gemini에게 요청하여 첫 상황 서술을 받습니다.
    try:
        # 첫 상황 서술을 위한 프롬프트
        first_turn_prompt = f"""당신은 인터랙티브 텍스트 어드벤처 게임의 게임 마스터입니다. 플레이어는 다음 스토리로 게임을 시작하고 싶어합니다: '{user_story_description}'. 이 스토리의 첫 상황을 서술해주세요. 답변은 200자 이내로 간결하게 작성하고, 다음 행동에 대한 몇 가지 선택지를 제시해주세요. 하지만 플레이어는 제시된 선택지 외에도 자유롭게 행동을 입력할 수 있습니다.

이 게임의 명확한 목표를 설정하고, 이를 'state_updates' 필드의 'current_goal'에 포함해주세요. 목표는 플레이어가 달성해야 할 구체적인 내용이어야 합니다.

응답은 오직 JSON 객체 하나만 포함해야 합니다. JSON은 코드 블록(```json ... ```)으로 감싸지 말고, 순수한 JSON 문자열만 반환해야 합니다. 'narrative' 필드에는 게임 서술과 선택지만 포함되어야 하며, 다른 JSON 구조나 메타 정보는 포함하지 마세요.

예시:
{{
  "narrative": "당신은 고대 유적의 입구에 서 있습니다. 거대한 돌문에는 알 수 없는 문자들이 새겨져 있고, 오래된 먼지 냄새가 코를 찌릅니다. 안에서는 희미한 빛이 새어 나옵니다.\n\n어떻게 하시겠습니까? (1) 돌문을 연다 (2) 주변을 탐색한다 (3) 유적을 떠난다",
  "state_updates": {{
    "location": "고대 유적 입구",
    "current_goal": "고대 유적의 비밀을 밝혀낸다"
  }}
}}
"""
        response = model.generate_content([{"role": "user", "parts": [first_turn_prompt]}])
        gemini_raw_response = response.text

        # JSON 파싱 로직 강화
        try:
            # 1. 먼저 원본 응답을 직접 JSON으로 파싱 시도
            gemini_parsed_response = json.loads(gemini_raw_response.strip())
            narrative = gemini_parsed_response.get("narrative", "")
            state_updates = gemini_parsed_response.get("state_updates", {})

        except json.JSONDecodeError:
            # 2. 직접 파싱 실패 시, 코드 블록에서 JSON 추출 시도
            json_match = re.search(r'```json\s*({.*?})\s*```', gemini_raw_response, re.DOTALL)
            if json_match:
                json_string = json_match.group(1)
                try:
                    gemini_parsed_response = json.loads(json_string)
                    narrative = gemini_parsed_response.get("narrative", "")
                    state_updates = gemini_parsed_response.get("state_updates", {})
                except json.JSONDecodeError:
                    # 코드 블록 내 JSON도 유효하지 않은 경우
                    narrative = gemini_raw_response # 원본 응답을 그대로 사용
                    print(f"Warning: Gemini returned a JSON code block, but its content was invalid. Raw response: {gemini_raw_response}")
            else:
                # 코드 블록도 없고 직접 파싱도 실패한 경우
                narrative = gemini_raw_response # 원본 응답을 그대로 사용
                print(f"Warning: Gemini did not return valid JSON and no JSON code block was found. Raw response: {gemini_raw_response}")
        except Exception as e: # JSON 추출/파싱 외의 다른 예외 처리
            narrative = gemini_raw_response # 원본 응답을 그대로 사용
            print(f"Warning: Unexpected error during JSON processing: {e}. Raw response: {gemini_raw_response}")

        # 플레이어 상태 업데이트 (파싱 성공 여부와 관계없이 시도)
        for key, value in state_updates.items():
            player_state[key] = value

        game_history.append({"role": "assistant", "content": narrative})

        return jsonify({"status": "success", "message": "Game started!", "initial_narrative": narrative, "player_state": player_state})

    except Exception as e:
        print(f"Error getting initial game narrative from Gemini: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/play', methods=['POST'])
def play_game():
    """사용자 입력을 받아 Gemini와 상호작용하고 응답을 반환합니다."""
    global game_phase
    if game_phase != "playing":
        return jsonify({"error": "Game is not in playing phase. Please start a story first."}), 400

    user_action = request.json.get('action')

    if not user_action:
        return jsonify({"error": "Action is required"}), 400

    global game_history
    global player_state
    global selected_story_initial_prompt

    game_rules = get_game_rules()

    # 최근 대화 기록을 프롬프트에 포함하기 위해 문자열로 구성
    recent_history_for_prompt = ""
    start_index = max(0, len(game_history) - (MAX_HISTORY_TURNS * 2))
    for i in range(start_index, len(game_history)):
        msg = game_history[i]
        if msg['role'] == 'user':
            recent_history_for_prompt += f"플레이어: {msg['content']}\n"
        else: # assistant
            recent_history_for_prompt += f"게임 마스터: {msg['content']}\n"

    # Gemini에게 보낼 프롬프트 구성
    prompt_content = f"""{selected_story_initial_prompt}

# 게임 규칙
{game_rules}

# 현재 플레이어 상태
{json.dumps(player_state, ensure_ascii=False, indent=2)}

# 최근 대화 기록 (가장 최근 {MAX_HISTORY_TURNS}턴)
{recent_history_for_prompt}

# 플레이어의 행동
{user_action}

위 정보를 바탕으로 다음 상황을 흥미진진하게 전개해주세요. 답변은 200자 이내로 간결하게 작성하고, 다음 행동에 대한 몇 가지 선택지를 제시해주세요. 하지만 플레이어는 제시된 선택지 외에도 자유롭게 행동을 입력할 수 있습니다.

응답은 오직 JSON 객체 하나만 포함해야 합니다. JSON은 코드 블록(```json ... ```)으로 감싸지 말고, 순수한 JSON 문자열만 반환해야 합니다. 'narrative' 필드에는 게임 서술과 선택지만 포함되어야 하며, 다른 JSON 구조나 메타 정보는 포함하지 마세요.

예시:
{{
  "narrative": "당신은 동굴 깊숙이 들어섰습니다. 어둠 속에서 거대한 그림자가 움직입니다. 드래곤이 당신을 발견했습니다!\n\n어떻게 하시겠습니까? (1) 드래곤에게 돌진한다 (2) 숨을 곳을 찾는다 (3) 도망친다",
  "state_updates": {{
    "location": "드래곤의 둥지",
    "health": 90,
    "status_effects": ["공포"]
  }}
}}
"""

    try:
        # Gemini API 호출 (단일 메시지로 모든 문맥 전달)
        response = model.generate_content([{"role": "user", "parts": [prompt_content]}])
        gemini_raw_response = response.text

        # JSON 파싱 로직 강화 (select_story와 동일하게 적용)
        try:
            gemini_parsed_response = json.loads(gemini_raw_response.strip())
            narrative = gemini_parsed_response.get("narrative", "")
            state_updates = gemini_parsed_response.get("state_updates", {})

        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*({.*?})\s*```', gemini_raw_response, re.DOTALL)
            if json_match:
                json_string = json_match.group(1)
                try:
                    gemini_parsed_response = json.loads(json_string)
                    narrative = gemini_parsed_response.get("narrative", "")
                    state_updates = gemini_parsed_response.get("state_updates", {})
                except json.JSONDecodeError:
                    narrative = gemini_raw_response
                    print(f"Warning: Gemini returned a JSON code block, but its content was invalid. Raw response: {gemini_raw_response}")
            else:
                narrative = gemini_raw_response
                print(f"Warning: Gemini did not return valid JSON and no JSON code block was found. Raw response: {gemini_raw_response}")
        except Exception as e:
            narrative = gemini_raw_response
            print(f"Warning: Unexpected error during JSON processing: {e}. Raw response: {gemini_raw_response}")

        # 플레이어 상태 업데이트 (파싱 성공 여부와 관계없이 시도)
        for key, value in state_updates.items():
            player_state[key] = value

        # --- 목표 달성 여부 확인 및 게임 종료 로직 추가 --- #
        game_over_narrative = None
        if player_state["current_goal"] and player_state["current_goal"] != "":
            goal_check_prompt = f"""Given the game's current state: {json.dumps(player_state, ensure_ascii=False)} and the latest narrative: '{narrative}', has the player achieved their goal: '{player_state["current_goal"]}? Respond ONLY with 'YES' or 'NO'."""
            goal_check_response = model.generate_content([{"role": "user", "parts": [goal_check_prompt]}])
            goal_achieved = goal_check_response.text.strip().upper()

            if goal_achieved == "YES":
                game_phase = "game_over"
                final_narrative_prompt = f"""The player has achieved their goal: '{player_state["current_goal"]}'. Based on the current player state: {json.dumps(player_state, ensure_ascii=False)} and the last narrative: '{narrative}', write a triumphant and conclusive ending for the game. Keep it concise, around 100-150 words. Do not ask for further actions. Do not include any JSON or special formatting, just the plain text ending."""
                final_narrative_response = model.generate_content([{"role": "user", "parts": [final_narrative_prompt]}])
                game_over_narrative = final_narrative_response.text.strip()

        # 게임 기록에 사용자 입력과 Gemini 응답 추가 (표시용)
        game_history.append({"role": "user", "content": user_action})
        game_history.append({"role": "assistant", "content": narrative})

        # 현재 플레이어 상태를 함께 반환
        response_data = {"response": narrative, "player_state": player_state}
        if game_over_narrative:
            response_data["game_over"] = True
            response_data["game_over_narrative"] = game_over_narrative
            response_data["final_player_state"] = player_state # 게임 종료 시 최종 상태

        return jsonify(response_data)

    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_game():
    """게임 상태를 초기화합니다."""
    global game_history
    global player_state
    global game_phase
    global selected_story_initial_prompt

    game_history = []
    player_state = {
        "location": "어두운 동굴 입구",
        "health": 100,
        "max_health": 100,
        "attack": 10,
        "defense": 5,
        "level": 1,
        "experience": 0,
        "inventory": [],
        "status_effects": [],
        "quest_progress": {},
        "current_goal": "" # 초기화 시 목표도 초기화
    }
    game_phase = "story_selection" # 게임 단계를 스토리 선택으로 리셋
    selected_story_initial_prompt = "" # 선택된 스토리 초기화

    return jsonify({"status": "success", "message": "Game reset successfully", "player_state": player_state, "game_phase": game_phase})
if __name__ == '__main__':
    # 개발 환경에서만 사용합니다. Cloud Run에서는 Gunicorn이 실행합니다.                │
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))