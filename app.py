import os
from dotenv import load_dotenv
import chess
import chess.engine
from flask import Flask, request, jsonify, render_template
from groq import Groq

# טעינת משתנים
load_dotenv()
app = Flask(__name__)

# --- נתיב למנוע ה-Stockfish שלך ---
STOCKFISH_PATH = r"C:\Users\Yoel kraitman\Desktop\projects\Chess_AI_Project\engine\stockfish.exe"

# הגדרות API של Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

PIECE_NAMES = {
    chess.PAWN: "רגלי", chess.KNIGHT: "סוס", chess.BISHOP: "רץ",
    chess.ROOK: "צריח", chess.QUEEN: "מלכה", chess.KING: "מלך"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_move():
    data = request.json
    fen_before = data.get('fen')
    move_uci = data.get('move')
    history = data.get('history', 'תחילת משחק')

    board = chess.Board(fen_before)
    move = chess.Move.from_uci(move_uci)
    
    # תרגום המהלך של השחקן
    moving_piece = board.piece_at(move.from_square)
    piece_name = PIECE_NAMES.get(moving_piece.piece_type, "כלי")
    action_str = f"{piece_name} ל-{chess.square_name(move.to_square)}"
            
    try:
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            # מה Stockfish חושב שהיה צריך לעשות?
            info_before = engine.analyse(board, chess.engine.Limit(time=0.5))
            best_move_uci = str(info_before.get("pv")[0]) if info_before.get("pv") else "N/A"
            
            best_action_str = "לא ידוע"
            if best_move_uci != "N/A":
                best_move_obj = chess.Move.from_uci(best_move_uci)
                best_engine_piece = board.piece_at(best_move_obj.from_square)
                engine_piece_name = PIECE_NAMES.get(best_engine_piece.piece_type, "כלי") if best_engine_piece else ""
                best_action_str = f"{engine_piece_name} ל-{chess.square_name(best_move_obj.to_square)}"

            # מבצעים את המהלך כדי לבדוק את הציון עכשיו
            board.push(move)
            info_after = engine.analyse(board, chess.engine.Limit(time=0.5))
            score_pov = info_after["score"].white()
            score_str = f"Mate in {score_pov.mate()}" if score_pov.is_mate() else f"{score_pov.score() / 100.0:+.2f}"

    except Exception as e:
        return jsonify({"error": f"Stockfish Error: {str(e)}"}), 500

    # הפרומפט שבונה את התשובה המושלמת שרצית
    prompt = f"""
    אתה מאמן שחמט רב-אמן. המטרה שלך היא ללמד אסטרטגיה עמוקה, במיוחד בפתיחות.
    
    נתונים:
    היסטוריית המשחק עד כה: {history}
    המהלך שבוצע הרגע: {action_str} ({move_uci})
    המלצת המנוע (אם בוצעה טעות): {best_action_str}
    ציון העמדה הנוכחי: {score_str}
    
    ענה בעברית בלבד, בפורמט HTML בדיוק לפי המבנה הבא. אל תוסיף הקדמות או סיכומי ביניים:
    
    <p><b>🎯 הלוגיקה העמוקה (ה"למה"):</b> הסבר בפירוט את הרעיון האסטרטגי. למה המהלך הזה שוחק דווקא עכשיו? מה הוא משיג (שליטה במרכז, לחץ, פינוי ערוגה)? אם זו טעות, הסבר מה הכשל הלוגי.</p>
    <p><b>💡 כלל ברזל לזיכרון:</b> תן טיפ קליט, משפט מפתח או עיקרון שחמטאי שיעזור לתלמיד לזהות את המצב הזה בעתיד (לדוגמה: "כשהיריב מוציא מלכה מוקדם, נפתח כלים תוך כדי תקיפתה").</p>
    <p><b>⚔️ איך להעניש:</b> בהנחה שהיריב יטעה או ישחק מהלך פסיבי עכשיו, איך ננצל את זה? מה התוכנית ההתקפית או הרצף הטקטי שצריך לחפש במהלך הבא?</p>
    
    חוקים נוקשים: אל תזכיר את המילה "מנוע" או מספרים סטטיסטיים. אל תמציא שמות של משבצות שלא קיימות (רק a1 עד h8).
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3
        )
        # שולחים רק את התוכן חזרה לדפדפן
        explanation = chat_completion.choices[0].message.content.strip()
        
        # מנקה פורמט Markdown במידה וה-AI מתעקש להוסיף אותו
        if explanation.startswith("```html"):
            explanation = explanation[7:]
        if explanation.endswith("```"):
            explanation = explanation[:-3]
            
        return jsonify({"explanation": explanation, "best_move": best_move_uci})
    except Exception as e:
        return jsonify({"error": f"AI Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)