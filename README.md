## 🎮 Diag-Tactics Arena

**Diag-Tactics Arena** is a two-player, zero-sum, perfect-information strategy board game built to test and compare adversarial search algorithms under dynamic environmental constraints.

### 🎲 Game Rules & Mechanics
*   **Grid Size:** Played on an $N \times N$ board (supports $5\times5$, $7\times7$, and $9\times9$).
*   **Win Condition:** Unlike traditional Connect-Four or Gobang, victory is achieved **strictly by aligning 4 consecutive pieces diagonally**.
*   **Two-Phase Gameplay:**
    1.  **DROP Phase:** Players alternately drop pieces into columns (with Connect-Four gravity) for a maximum of 4 drops each.
    2.  **MOVE Phase:** Players shift to relocating their existing pieces to orthogonally adjacent empty, non-hazard cells.

### ⚡ Dynamic Hazard System
To introduce a non-stationary search space, **dynamic hazard cells** regenerate after every single move. A threat-aware probabilistic policy spawns these hazards to actively block near-complete diagonals, forcing AI agents to constantly adapt their strategies.

### 🤖 AI Agent Profiles & Personalities
The game features depth-limited **Minimax** and **Alpha-Beta Pruning** agents. By tuning the heuristic weights (diagonal potential, piece mobility, and hazard proximity penalties), the agents can exhibit distinct behavioral styles:
*   **Balanced:** Equal priority to attack, defense, and hazard avoidance.
*   **Aggressive:** Prioritizes diagonal-building and mobility while discounting hazard risks.
*   **Defensive:** Maximizes safety and prioritizes hazard avoidance.
*   **Random:** Injects stochastic noise into the evaluation for unpredictable play.
