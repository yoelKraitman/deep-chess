import os
import chess
import chess.engine
from groq import Groq

# --- 1. SETTINGS ---
STOCKFISH_PATH = r"C:\Users\Yoel kraitman\Desktop\projects\Chess_AI_Project\engine\stockfish.exe"
# Security Note: It is recommended to keep your API key in an environment variable later on.
GROQ_API_KEY = "KEY" 

client = Groq(api_key=GROQ_API_KEY)

def get_chess_analysis():
    if not os.path.exists(STOCKFISH_PATH):
        print("❌ Error: Stockfish engine not found at the specified path.")
        return

    board = chess.Board()
    my_move_uci = "e2e4"
    board.push_uci(my_move_uci)

    print(f"✅ Analyzing move: {my_move_uci}...")

    # Stockfish Analysis
    try:
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            info = engine.analyse(board, chess.engine.Limit(time=0.5))
            score = info["score"].relative
            best_move = info.get("pv")[0] if info.get("pv") else "N/A"
    except Exception as e:
        print(f"❌ Stockfish Error: {e}")
        return

    print("🤖 Requesting AI explanation from Groq (Llama 3.3)...")

    prompt = f"""
    You are a Chess Grandmaster. 
    Board (FEN): {board.fen()}
    Move played: {my_move_uci}
    Score: {score}
    Best move: {best_move}
    
    Explain in 2 concise sentences in ENGLISH why this move is strategically sound 
    and how it influences center control.
    """

    try:
        # Using llama-3.3-70b-versatile for high-quality analysis
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        
        print("\n" + "="*50)
        print("MOVE ANALYSIS (Groq AI):")
        print(chat_completion.choices[0].message.content)
        print("="*50)
        
    except Exception as e:
        print(f"❌ AI Error: {e}")

if __name__ == "__main__":
    get_chess_analysis()