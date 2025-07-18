import os
import json
import re
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

app = Flask(__name__)

# Google Gemini API 키 설정
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# --- 글로벌 변수 ---
# 게임의 핵심 상태를 관리합니다.
DEFAULT_PLAYER_STATE = {
    "location": "알 수 없는 곳",
    "health": 100,
    "max_health": 100,
    "attack": 10,
    "defense": 5,
    "level": 1,
    "experience": 0,
    "inventory": [],
    "status_effects": [],
    "quest_progress": {},
    "current_goal": ""
}
player_state = DEFAULT_PLAYER_STATE.copy()
game_phase = "story_selection"
game_chat_session = None # AI와의 대화 세션을 저장할 변수

# Gemini 모델 초기화
# safety_settings를 통해 유해성 응답 차단 레벨을 조정할 수 있습니다.
model = genai.GenerativeModel('gemini-1.5-flash')

def get_game_rules():
    """game_rules2.md 파일에서 규칙을 읽어옵니다."""
    try:
        with open("game_rules2.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: game_rules2.md not found. Using empty rules.")
        return ""

def parse_gemini_response(gemini_raw_response):
    """Gemini의 응답(순수 JSON 또는 마크다운 코드 블록)을 파싱합니다."""
    try:
        # 가장 일반적인 경우: 순수한 JSON 문자열
        return json.loads(gemini_raw_response.strip())
    except json.JSONDecodeError:
        # 두 번째 경우: 마크다운 코드 블록(```json ... ```) 안에 JSON이 있는 경우
        json_match = re.search(r'```json\s*({.*?})\s*```', gemini_raw_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                print(f"Warning: Invalid JSON inside code block. Raw: {gemini_raw_response}")
                # JSON 구조가 깨졌더라도 서술 부분만이라도 반환 시도
                return {"narrative": gemini_raw_response, "state_updates": {}}
        else:
            # 마지막 경우: JSON 형식이 아닌 일반 텍스트 응답
            print(f"Warning: Non-JSON response from Gemini. Raw: {gemini_raw_response}")
            return {"narrative": gemini_raw_response, "state_updates": {}}

def update_player_state(updates):
    """플레이어 상태를 업데이트합니다. 리스트는 추가, 나머지는 덮어쓰기."""
    if not updates:
        return
    for key, value in updates.items():
        if key in player_state and isinstance(player_state[key], list):
            # 인벤토리나 상태 효과 같은 리스트는 요소를 추가합니다.
            if isinstance(value, list):
                player_state[key].extend(value)
            else:
                player_state[key].append(value)
        else:
            # 다른 모든 값은 덮어씁니다.
            player_state[key] = value

@app.route('/')
def index():
    """메인 UI를 렌더링합니다."""
    return render_template('index.html')

@app.route('/select_story', methods=['POST'])
def select_story():
    """플레이어 설정으로 새 게임 세션을 시작합니다."""
    global game_phase, player_state, game_chat_session

    if game_phase != "story_selection":
        return jsonify({"error": "Game is already in progress."}), 400

    settings = request.json
    if not all(settings.values()):
        return jsonify({"error": "All settings and a story description are required."}), 400

    # --- 시스템 프롬프트 정의 ---
    # AI에게 게임의 규칙과 설정을 알려주는 부분. 세션이 시작될 때 한 번만 전송됩니다.
    game_rules = get_game_rules()
    system_prompt = f"""당신은 다음 [게임 설정]과 [게임 마스터 핵심 지침]에 따라 인터랙티브 텍스트 어드벤처 게임을 진행하는 게임 마스터(GM)입니다. 이 규칙들을 절대적으로 준수해야 합니다.

# [게임 설정]
- GM 성격: {settings['gm_personality']}
- 게임 장르: {settings['genre']}
- 난이도: {settings['difficulty']}
- 플레이어 역할: {settings['player_role']}
- 최종 목표: {settings['game_goal']}

# [게임 시작 스토리]
{settings['story_description']}

# [게임 마스터 핵심 지침]
{game_rules}
"""

    # --- 게임 상태 초기화 ---
    player_state = DEFAULT_PLAYER_STATE.copy()
    player_state["current_goal"] = settings['game_goal']

    try:
        # --- 새 대화 세션 시작 ---
        # 시스템 프롬프트를 모델에 주입하여 새로운 대화 세션을 생성합니다.
        game_chat_session = model.start_chat(
            history=[
                {"role": "user", "parts": [system_prompt]},
                {"role": "model", "parts": ["알겠습니다. 지금부터 플레이어가 설정한 규칙과 스토리에 따라 게임 마스터 역할을 시작하겠습니다."]}
            ]
        )

        # --- 게임의 첫 턴 시작 ---
        first_turn_prompt = f"""이제 게임을 시작합니다. 위 설정에 맞춰 게임의 첫 상황을 서술해주세요. 플레이어의 역할({settings['player_role']})과 시작 스토리를 반영하여 흥미로운 첫 장면을 묘사해야 합니다.

응답은 반드시 JSON 형식이어야 하며, 다음 두 개의 키를 포함해야 합니다:
1.  `narrative`: 플레이어에게 보여줄 게임 서술과 선택지.
2.  `state_updates`: 게임 시작 시 변경될 플레이어의 초기 상태 (예: 시작 위치, 기본 아이템).

예시:
{{
  "narrative": "당신은 {settings['player_role']}입니다. 기억을 잃은 채, 축축하고 어두운 동굴 안에서 눈을 뜹니다. 멀리서 물방울 떨어지는 소리가 들려옵니다.\n\n어떻게 하시겠습니까? (1) 주변을 더듬어 본다 (2) 소리가 들리는 쪽으로 가본다",
  "state_updates": {{
    "location": "어두운 동굴",
    "inventory": ["낡은 천옷"]
  }}
}}
"""
        response = game_chat_session.send_message(first_turn_prompt)
        parsed_response = parse_gemini_response(response.text)

        narrative = parsed_response.get("narrative", "오류: 게임 시작에 실패했습니다.")
        state_updates = parsed_response.get("state_updates", {})
        update_player_state(state_updates)

        game_phase = "playing"
        return jsonify({"status": "success", "message": "Game started!", "initial_narrative": narrative, "player_state": player_state})

    except Exception as e:
        print(f"Error starting game session: {e}")
        return jsonify({"error": f"Failed to start game session: {e}"}), 500

@app.route('/play', methods=['POST'])
def play_game():
    """진행 중인 게임 세션에 사용자 입력을 보내고 결과를 받습니다."""
    global game_phase, player_state, game_chat_session

    if game_phase != "playing":
        return jsonify({"error": "Game is not in playing phase."}), 400
    if not game_chat_session:
        return jsonify({"error": "Game session not found."}), 400

    user_action = request.json.get('action')
    if not user_action:
        return jsonify({"error": "Action is required"}), 400

    # --- AI에게 보낼 프롬프트 (훨씬 간결해짐) ---
    prompt = f"""
# 현재 플레이어 상태
{json.dumps(player_state, ensure_ascii=False, indent=2)}

# 플레이어의 행동
{user_action}

위 정보를 바탕으로 다음 상황을 전개해주세요. 응답은 반드시 `narrative`와 `state_updates` 키를 포함하는 JSON 형식이어야 합니다.
"""

    try:
        response = game_chat_session.send_message(prompt)
        parsed_response = parse_gemini_response(response.text)

        narrative = parsed_response.get("narrative", "오류: 응답을 처리할 수 없습니다.")
        state_updates = parsed_response.get("state_updates", {})
        update_player_state(state_updates)

        # 게임 종료 조건 확인
        if state_updates.get("game_over"):
            game_phase = "game_over"
            return jsonify({
                "response": narrative,
                "player_state": player_state,
                "game_over": True,
                "game_over_narrative": narrative # 종료 메시지는 narrative에 포함
            })

        return jsonify({"response": narrative, "player_state": player_state})

    except Exception as e:
        print(f"Error during play: {e}")
        return jsonify({"error": f"An error occurred during play: {e}"}), 500

@app.route('/reset', methods=['POST'])
def reset_game():
    """모든 게임 상태와 대화 세션을 초기화합니다."""
    global game_phase, player_state, game_chat_session
    
    player_state = DEFAULT_PLAYER_STATE.copy()
    game_phase = "story_selection"
    game_chat_session = None # 대화 세션 초기화

    print(f"DEBUG: reset_game - Player state after reset: {player_state}")
    return jsonify({"status": "success", "message": "Game reset successfully.", "player_state": player_state})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

@app.route('/get_save_data', methods=['GET'])
def get_save_data():
    """현재 게임 상태와 대화 기록을 JSON으로 반환합니다."""
    if game_phase != "playing" or not game_chat_session:
        print(f"DEBUG: get_save_data - game_phase: {game_phase}, game_chat_session: {game_chat_session is not None}")
        return jsonify({"error": "No active game to save."}), 400

    try:
        history_to_save = []
        if game_chat_session and game_chat_session.history:
            print(f"DEBUG: get_save_data - game_chat_session.history length: {len(game_chat_session.history)}")
            for i, message in enumerate(game_chat_session.history):
                try:
                    # message.parts가 비어있을 경우를 대비하여 확인
                    parts_text = [part.text for part in message.parts if hasattr(part, 'text')]
                    history_to_save.append({
                        "role": message.role,
                        "parts": parts_text
                    })
                    print(f"DEBUG: get_save_data - Message {i} processed. Role: {message.role}, Parts length: {len(parts_text)}")
                except Exception as part_e:
                    print(f"ERROR: get_save_data - Failed to process message part {i}: {part_e}")
                    # 문제가 있는 메시지는 건너뛰거나 기본값으로 처리
                    history_to_save.append({"role": message.role, "parts": ["[Error: Corrupted message]"]})

        save_data = {
            "player_state": player_state,
            "chat_history": history_to_save
        }
        print(f"DEBUG: get_save_data - Save data prepared. Player state keys: {player_state.keys()}, History length: {len(history_to_save)}")
        return jsonify(save_data)
    except Exception as e:
        print(f"ERROR: get_save_data - Unexpected error: {e}")
        return jsonify({"error": f"Failed to prepare save data: {e}"}), 500

@app.route('/load_game', methods=['POST'])
def load_game():
    """업로드된 JSON 파일로 게임 상태와 대화 세션을 복원합니다."""
    global game_phase, player_state, game_chat_session

    if 'save_file' not in request.files:
        return jsonify({"error": "No save file provided."}), 400

    file = request.files['save_file']
    if file.filename == '' or not file.filename.endswith('.json'):
        return jsonify({"error": "Invalid file. Please upload a .json save file."}), 400

    try:
        save_data = json.load(file)
        print(f"DEBUG: load_game - Received save data keys: {save_data.keys()}")
        
        # 데이터 유효성 검사
        if "player_state" not in save_data or "chat_history" not in save_data:
            print("ERROR: load_game - Invalid save file structure.")
            return jsonify({"error": "Invalid save file structure."}), 400

        # 게임 상태 복원
        global player_state # 전역 변수임을 명시
        player_state = save_data["player_state"]
        print(f"DEBUG: load_game - Player state restored: {player_state}")
        
        # 대화 세션 복원
        # 저장된 history를 genai.ChatSession이 요구하는 형식으로 재구성
        history_from_save = []
        for i, item in enumerate(save_data["chat_history"]):
            try:
                # parts가 리스트가 아닐 경우를 대비하여 확인
                parts_list = item['parts'] if isinstance(item['parts'], list) else [item['parts']]
                history_from_save.append({
                    "role": item['role'],
                    "parts": parts_list
                })
                print(f"DEBUG: load_game - History item {i} processed. Role: {item['role']}, Parts length: {len(parts_list)}")
            except Exception as hist_e:
                print(f"ERROR: load_game - Failed to process history item {i}: {hist_e}")
                # 문제가 있는 기록은 건너뛰거나 기본값으로 처리
                history_from_save.append({"role": item['role'], "parts": ["[Error: Corrupted history item]"]})

        global game_chat_session # 전역 변수임을 명시
        game_chat_session = model.start_chat(history=history_from_save)
        game_phase = "playing"
        print(f"DEBUG: load_game - Chat session restored with {len(history_from_save)} messages.")

        # 복원된 마지막 대화 내용을 클라이언트에 전달
        last_narrative = ""
        if game_chat_session.history and game_chat_session.history[-1].role == "model":
            # 마지막 메시지가 모델의 응답일 경우, 해당 내용을 파싱하여 전달
            parsed_response = parse_gemini_response(game_chat_session.history[-1].parts[0].text)
            last_narrative = parsed_response.get("narrative", "게임이 성공적으로 불러와졌습니다.")
        else:
            last_narrative = "게임이 성공적으로 불러와졌습니다. 이제 당신의 행동을 입력해주세요."

        print(f"DEBUG: load_game - Sending response to client. Narrative length: {len(last_narrative)}")
        return jsonify({
            "status": "success",
            "message": "Game loaded successfully!",
            "loaded_narrative": last_narrative,
            "player_state": player_state
        })

    except json.JSONDecodeError:
        print("ERROR: load_game - Failed to decode save file. It might be corrupted.")
        return jsonify({"error": "Failed to decode save file. It might be corrupted."}), 400
    except Exception as e:
        print(f"ERROR: load_game - Unexpected error: {e}")
        return jsonify({"error": f"An unexpected error occurred while loading: {e}"}), 500

# 전역 오류 핸들러: 처리되지 않은 모든 예외를 JSON 응답으로 변환
@app.errorhandler(Exception)
def handle_exception(e):
    # 프로덕션 환경에서는 e.name, e.description 대신 일반적인 메시지를 사용
    # 개발 환경에서는 디버깅을 위해 상세 정보를 포함할 수 있음
    response = {"error": "An unexpected server error occurred.", "details": str(e)}
    # HTTP 상태 코드 설정 (기본 500 Internal Server Error)
    status_code = getattr(e, 'code', 500)
    return jsonify(response), status_code
