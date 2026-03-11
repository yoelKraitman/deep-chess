import os
import chess
import chess.engine
from flask import Flask, request, jsonify, render_template
from groq import Groq

app = Flask(__name__)

# --- הגדרות ---
STOCKFISH_PATH = r"C:\Users\Yoel kraitman\Desktop\projects\Chess_AI_Project\engine\stockfish.exe"
GROQ_API_KEY = "KEY" # <--- שים את המפתח שלך כאן!
client = Groq(api_key=GROQ_API_KEY)

PIECE_NAMES = {
    chess.PAWN: "רגלי", chess.KNIGHT: "סוס", chess.BISHOP: "רץ",
    chess.ROOK: "צריח", chess.QUEEN: "מלכה", chess.KING: "מלך"
}
COLOR_NAMES = {
    chess.WHITE: "לבן", chess.BLACK: "שחור"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_move():
    data = request.json
    fen_before = data.get('fen')
    move_uci = data.get('move')

    board = chess.Board(fen_before)
    move = chess.Move.from_uci(move_uci)
    
    # 1. תרגום המהלך של השחקן לעברית
    moving_piece = board.piece_at(move.from_square)
    piece_name = PIECE_NAMES.get(moving_piece.piece_type, "כלי")
    piece_color = COLOR_NAMES.get(moving_piece.color, "")
    
    is_capture = board.is_capture(move)
    captured_piece = board.piece_at(move.to_square) if is_capture and not board.is_en_passant(move) else None
    
    action_str = f"הזזתי {piece_name} {piece_color} מ-{chess.square_name(move.from_square)} ל-{chess.square_name(move.to_square)}."
    if is_capture:
        if captured_piece:
            cap_name = PIECE_NAMES.get(captured_piece.piece_type, "כלי")
            cap_color = COLOR_NAMES.get(captured_piece.color, "")
            action_str += f" באותו מהלך אכלתי {cap_name} {cap_color} של היריב!"
        else:
            action_str += " באותו מהלך אכלתי דרך הילוכו!"
            
    try:
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            # מנתחים את העמדה לפני שהשחקן עשה את המהלך
            info_before = engine.analyse(board, chess.engine.Limit(time=0.5))
            best_move_uci = str(info_before.get("pv")[0]) if info_before.get("pv") else "N/A"
            
            # 2. תרגום המהלך של *המנוע* לעברית!
            best_action_str = "לא ידוע"
            if best_move_uci != "N/A":
                best_move_obj = chess.Move.from_uci(best_move_uci)
                best_engine_piece = board.piece_at(best_move_obj.from_square)
                if best_engine_piece:
                    engine_piece_name = PIECE_NAMES.get(best_engine_piece.piece_type, "כלי")
                    best_action_str = f"{engine_piece_name} ל-{chess.square_name(best_move_obj.to_square)}"
                else:
                    best_action_str = best_move_uci

            # מעדכנים את הלוח עם המהלך של השחקן כדי לקבל את הציון החדש
            board.push(move)
            info_after = engine.analyse(board, chess.engine.Limit(time=0.5))
            
            score_pov = info_after["score"].white()
            if score_pov.is_mate():
                score_str = f"Mate in {score_pov.mate()}"
            else:
                score_str = f"{score_pov.score() / 100.0:+.2f}"

    except Exception as e:
        return jsonify({"error": f"Stockfish Error: {str(e)}"}), 500

    # 3. הפרומפט החדש והקשוח - מחייב הסבר אמיתי!
    prompt = f"""
    אתה מאמן שחמט בכיר שמנתח משחק של תלמיד. 
    
    חוקים נוקשים לתשובה שלך:
    1. **אסור** לך להשתמש במילים "המנוע המליץ", "לפי Stockfish", או "הציון הוא". אל תדבר על מספרים.
    2. אתה חייב להסביר את ה*למה* (שליטה במרכז, פיתוח כלים, חולשות, איומים טקטיים, בטיחות המלך).
    3. תסביר מדוע המהלך החלופי עדיף רעיונית. המטרה היא לבנות הבנה, לא לשנן מהלכים.
    
    נתונים:
    מצב הלוח: {board.fen()}
    המהלך שהתלמיד ביצע כרגע: {action_str}
    המהלך הנכון שהיה עליו לבצע במקום זאת: {best_action_str}
    
    כתוב פסקת הסבר אחת, חדה וברורה בעברית, שנותנת לתלמיד תובנה אמיתית על העמדה ועל ההבדל בין המהלכים.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        explanation = chat_completion.choices[0].message.content
        return jsonify({"explanation": explanation, "best_move": best_move_uci})
    except Exception as e:
        return jsonify({"error": f"AI Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)