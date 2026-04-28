import os
from dotenv import load_dotenv
import chess
import chess.engine
from flask import Flask, request, jsonify, render_template
from groq import Groq

load_dotenv()
app = Flask(__name__)

STOCKFISH_PATH = r"C:\Users\Yoel kraitman\Desktop\projects\Chess_AI_Project\engine\stockfish.exe"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

PIECE_NAMES = {
    chess.PAWN: "רגלי", chess.KNIGHT: "סוס", chess.BISHOP: "רץ",
    chess.ROOK: "צריח", chess.QUEEN: "מלכה", chess.KING: "מלך"
}


def score_to_cp(score_obj):
    if score_obj.is_mate():
        m = score_obj.mate()
        return 10000 if m > 0 else -10000
    return score_obj.score() or 0


def classify_move(cp_loss):
    if cp_loss < -50:
        return "brilliant", "✨ מהלך מבריק"
    elif cp_loss <= 20:
        return "good", "✅ מהלך טוב"
    elif cp_loss <= 100:
        return "inaccuracy", "⚠️ אי-דיוק"
    elif cp_loss <= 300:
        return "mistake", "❌ טעות"
    else:
        return "blunder", "💀 בלאנדר!"


def get_top_moves(engine, board, n=3):
    results = engine.analyse(board, chess.engine.Limit(time=0.8), multipv=n)
    moves = []
    for info in results:
        if not info.get("pv"):
            continue
        m = info["pv"][0]
        sc = info["score"].relative
        if sc.is_mate():
            sc_str = f"מט ב-{abs(sc.mate())}"
        else:
            sc_str = f"{sc.score() / 100.0:+.2f}"
        moves.append({"uci": str(m), "san": board.san(m), "score": sc_str})
    return moves


def get_continuation(engine, board, depth=5):
    info = engine.analyse(board, chess.engine.Limit(time=0.5))
    pv = info.get("pv", [])[:depth]
    sans = []
    b = board.copy()
    for m in pv:
        sans.append(b.san(m))
        b.push(m)
    return " ".join(sans)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze_move():
    data = request.json
    fen_before = data.get('fen')
    move_uci = data.get('move')
    history = data.get('history', 'תחילת משחק')
    move_number = int(data.get('move_number', 1))

    board = chess.Board(fen_before)
    move = chess.Move.from_uci(move_uci)

    white_to_move = board.turn == chess.WHITE
    mover_color = "לבן" if white_to_move else "שחור"

    moving_piece = board.piece_at(move.from_square)
    piece_name = PIECE_NAMES.get(moving_piece.piece_type, "כלי")
    from_sq = chess.square_name(move.from_square)
    to_sq = chess.square_name(move.to_square)
    action_str = f"{piece_name} מ-{from_sq} ל-{to_sq}"
    move_san = board.san(move)

    if move_number <= 15:
        phase = "opening"
        phase_he = "פתיחה"
    elif move_number <= 35:
        phase = "middlegame"
        phase_he = "ביניים"
    else:
        phase = "endgame"
        phase_he = "סיום"

    try:
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            # Score from white's perspective before the move
            info_before = engine.analyse(board, chess.engine.Limit(time=0.5))
            score_before_white_cp = score_to_cp(info_before["score"].white())
            score_before_mover_cp = score_before_white_cp if white_to_move else -score_before_white_cp

            # Top 3 moves before the move was played
            top_moves = get_top_moves(engine, board, 3)
            best_move_uci = top_moves[0]["uci"] if top_moves else "N/A"
            best_move_san = top_moves[0]["san"] if top_moves else "?"

            # Execute the move
            board.push(move)

            # Score from white's perspective after the move
            info_after = engine.analyse(board, chess.engine.Limit(time=0.5))
            score_after_white_cp = score_to_cp(info_after["score"].white())
            score_after_mover_cp = score_after_white_cp if white_to_move else -score_after_white_cp

            # Best continuation line after the move was played
            continuation = get_continuation(engine, board, 6)

            # Positive cp_loss = mover played worse than best; negative = improvement
            cp_loss = score_before_mover_cp - score_after_mover_cp

            mistake_type, mistake_label = classify_move(cp_loss)

            def fmt(cp):
                if abs(cp) >= 9000:
                    return "מט" if cp > 0 else "מט-"
                return f"{cp / 100.0:+.2f}"

            score_before_str = fmt(score_before_mover_cp)
            score_after_str = fmt(score_after_mover_cp)
            top_moves_str = "\n".join(f"- {m['san']} ({m['score']})" for m in top_moves)

    except Exception as e:
        return jsonify({"error": f"Stockfish Error: {str(e)}"}), 500

    is_mistake = mistake_type in ("inaccuracy", "mistake", "blunder")

    if phase == "opening":
        phase_ctx = """
בשלב הפתיחה, התמקד ב:
- האם המהלך מפתח כלים? שולט במרכז (e4,d4,e5,d5)? מכין רוקאדה?
- מה הרעיון התיאורטי - מה עקרון הפתיחה שמאחורי המהלך?
- אם זו סטייה מהתיאוריה - מה בדיוק לא בסדר בה, ואיך מענישים אותה צעד אחר צעד?
"""
    elif phase == "middlegame":
        phase_ctx = """
בשלב הביניים, התמקד ב:
- מה החולשה הטקטית/האסטרטגית שנוצרה? (משבצת חלשה, ערוגה פתוחה, מלך חשוף, כלי תלוי)
- האם יש רצף טקטי? (מזלג, סיכה, שח כפול, מלכודת)
- מה הצעדים המדויקים שמנצלים את הטעות?
"""
    else:
        phase_ctx = """
בסיום, התמקד ב:
- איך משפיע המהלך על מבנה הרגלים ויתרון הכלים?
- האם המלך פעיל? אינו כלי לגיטימי בסיום?
- מה המסלול הספציפי לניצחון או להצלה?
"""

    if is_mistake:
        punishment_block = f"""
המהלך שהיה צריך לשחק: {best_move_san}
ההמשך הטוב ביותר אחרי הטעות: {continuation}

בסעיף ⚔️ תוכנית הענישה - כתוב צעדים ממוספרים בדיוק: "1. [מהלך] כי [סיבה]. 2. [מהלך] ואז..." עם שמות משבצות ספציפיים (a1-h8).
"""
    else:
        punishment_block = f"""
המהלך הטוב ביותר: {best_move_san}
המשך הניתוח: {continuation}

בסעיף 🔮 התוכנית קדימה - הסבר מה לתכנן עכשיו אסטרטגית.
"""

    prompt = f"""
אתה גרנד-מאסטר שחמט ומאמן מקצועי. ענה בעברית בלבד, בפורמט HTML בלבד.

=== נתוני המשחק ===
מי שיחק: {mover_color}
המהלך: {action_str} (בסימון: {move_san})
שלב: {phase_he} (מהלך מספר {move_number})
ציון לפני: {score_before_str} → ציון אחרי: {score_after_str}
איכות המהלך: {mistake_label} (הפרש: {abs(cp_loss) / 100.0:.1f} יחידות)

המהלכים הטובים ביותר שניתן היה לשחק:
{top_moves_str}

היסטוריית המשחק: {history}
{phase_ctx}
{punishment_block}

=== פורמט התשובה הדרוש (אל תוסיף שום דבר מחוץ לתגיות) ===

<p><b>🎯 הלוגיקה העמוקה:</b> [הסבר WHY - מה הרעיון מאחורי המהלך, מה משתנה בעמדה, מה הסכנה שנוצרת]</p>
<p><b>💡 כלל ברזל:</b> [עיקרון שחמטאי אחד ממצה וקצר שקל לזכור לכל החיים]</p>
<p><b>{'⚔️ תוכנית הענישה' if is_mistake else '🔮 התוכנית קדימה'}:</b> [{'צעדים ממוספרים מדויקים לניצול הטעות עם שמות משבצות' if is_mistake else 'האסטרטגיה הנכונה מכאן'}]</p>

חוקים נוקשים: (1) אל תזכיר "מנוע" אף פעם. (2) השתמש רק במשבצות שקיימות: a1 עד h8. (3) אל תמציא מהלכים.
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3
        )
        explanation = chat_completion.choices[0].message.content.strip()
        if explanation.startswith("```html"):
            explanation = explanation[7:]
        if explanation.endswith("```"):
            explanation = explanation[:-3]
        explanation = explanation.strip()

        return jsonify({
            "explanation": explanation,
            "best_move": best_move_uci,
            "mistake_type": mistake_type,
            "mistake_label": mistake_label,
            "cp_loss": cp_loss,
            "score_white_cp": score_after_white_cp,
        })
    except Exception as e:
        return jsonify({"error": f"AI Error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
