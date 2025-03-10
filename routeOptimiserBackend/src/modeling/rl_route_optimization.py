# src/modeling/rl_route_optimization.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import gymnasium as gym
import numpy as np
import networkx as nx
import pickle
import logging
from typing import Tuple
from gymnasium import spaces
from stable_baselines3 import DQN, PPO
from stable_baselines3.common.evaluation import evaluate_policy
from src.utils.helpers import load_config, haversine_distance, get_node_coords

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RouteEnv(gym.Env):
    def __init__(self, G: nx.MultiDiGraph, start: str, goal: str, time_budget: float = 1000.0, max_steps: int = 20):
        super(RouteEnv, self).__init__()
        self.G = G
        self.start = start
        self.goal = goal
        self.time_budget = time_budget  # Increased to 1000 hours
        self.max_steps = max_steps  # Cap episode length
        self.current = start
        self.cumulative_cost = 0.0
        self.cumulative_time = 0.0
        self.cumulative_emissions = 0.0
        self.visited = set()
        self.step_count = 0

        # Normalize edge attributes
        self.max_cost = max([d.get("cost", 0) for _, _, d in G.edges(data=True)]) or 1.0
        self.max_time = max([d.get("time", 0) for _, _, d in G.edges(data=True)]) or 1.0
        self.max_emissions = max([d.get("emissions", 0) for _, _, d in G.edges(data=True)]) or 1.0
        logger.info(f"Max cost: {self.max_cost}, Max time: {self.max_time}, Max emissions: {self.max_emissions}")

        self._update_action_space()
        self.observation_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.0, 0.0]),
            high=np.array([1e3, 1e3, 1e3, 1e4]),
            dtype=np.float32
        )

    def _update_action_space(self):
        edges = list(self.G.edges(self.current, data=True))
        self.action_space = spaces.Discrete(len(edges) if edges else 1)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        self.step_count += 1
        edges = list(self.G.edges(self.current, data=True))
        if not edges:
            reward = -10.0
            terminated = True
            truncated = False
            obs = self._get_obs()
            return obs, reward, terminated, truncated, {"info": "No outgoing edges"}

        try:
            edge = edges[action]
        except IndexError:
            logger.warning(f"Invalid action {action}. Choosing first edge.")
            edge = edges[0]

        next_node = edge[1]
        edge_data = edge[2]
        cost = edge_data.get("cost", 0.0) / self.max_cost
        time = edge_data.get("time", 0.0) / self.max_time
        emissions = edge_data.get("emissions", 0.0) / self.max_emissions

        self.cumulative_cost += cost
        self.cumulative_time += time
        self.cumulative_emissions += emissions
        self.current = next_node
        self.visited.add(next_node)
        self._update_action_space()

        # Distance-based reward shaping
        curr_coords = get_node_coords(self.G.nodes[self.current])
        goal_coords = get_node_coords(self.G.nodes[self.goal])
        dist_to_goal = haversine_distance(curr_coords, goal_coords) if curr_coords and goal_coords else 0.0
        prev_dist = self._get_obs()[3]  # Previous distance from obs
        distance_reward = (prev_dist - dist_to_goal) / 1000.0  # Scale to small positive/negative

        # Reward calculation
        reward = -(self.w1 * cost + self.w2 * time + self.w3 * emissions) * 10 + distance_reward
        terminated = False
        truncated = False

        if self.current == self.goal:
            reward += 100.0
            terminated = True
        elif self.cumulative_time > (self.time_budget / self.max_time):  # Normalized budget
            reward -= 5.0
            truncated = True
        elif self.step_count >= self.max_steps:
            reward -= 10.0
            truncated = True

        obs = self._get_obs()
        info = {
            "current_node": self.current,
            "path": list(self.visited),
            "raw_cost": edge_data.get("cost", 0.0),
            "raw_time": edge_data.get("time", 0.0),
            "raw_emissions": edge_data.get("emissions", 0.0),
            "dist_to_goal": dist_to_goal
        }
        return obs, reward, terminated, truncated, info

    def reset(self, *, seed: int = None, options: dict = None) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.current = self.start
        self.cumulative_cost = 0.0
        self.cumulative_time = 0.0
        self.cumulative_emissions = 0.0
        self.visited = {self.start}
        self.step_count = 0
        self._update_action_space()
        return self._get_obs(), {}

    def _get_obs(self) -> np.ndarray:
        coords = get_node_coords(self.G.nodes[self.current])
        goal_coords = get_node_coords(self.G.nodes[self.goal])
        dist_to_goal = haversine_distance(coords, goal_coords) if coords and goal_coords else 0.0
        return np.array([
            self.cumulative_cost,
            self.cumulative_time,
            self.cumulative_emissions,
            dist_to_goal
        ], dtype=np.float32)

def load_graph(graph_path: str) -> nx.MultiDiGraph:
    with open(graph_path, "rb") as f:
        G = pickle.load(f)
    logger.info(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    return G

def train_ppo_agent(G: nx.MultiDiGraph, start: str, goal: str, timesteps: int = 100000) -> PPO:
    env = RouteEnv(G, start, goal)
    env.w1, env.w2, env.w3 = 0.2, 0.2, 0.6
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.01,  # Encourage exploration
        verbose=1
    )
    logger.info(f"Training PPO agent for {timesteps} timesteps.")
    model.learn(total_timesteps=timesteps)
    model.save("ppo_carbon_optimizer")
    logger.info("PPO training completed.")
    return model

def evaluate_agent(model, env: RouteEnv, episodes: int = 10) -> list:
    paths = []
    mean_reward, _ = evaluate_policy(model, env, n_eval_episodes=episodes, deterministic=True)
    logger.info(f"Mean reward over {episodes} episodes: {mean_reward}")

    for i in range(episodes):
        obs, _ = env.reset()
        done = False
        path = [env.start]
        total_cost, total_time, total_emissions = 0.0, 0.0, 0.0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            path.append(env.current)
            total_cost += info["raw_cost"]
            total_time += info["raw_time"]
            total_emissions += info["raw_emissions"]
        paths.append(path)
        logger.info(f"Episode {i+1} - Cost: {total_cost:.2f}, Time: {total_time:.2f} hours, Emissions: {total_emissions:.2f} kg CO₂")
    return paths

def main():
    config = load_config()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    graph_path = os.path.join(project_root, config["data"]["processed_dir"], config["graph"]["output_file"])
    
    G = load_graph(graph_path)
    start_node = "Custom_40.7128_-74.006_general"  # New York
    goal_node = "Custom_51.5074_-0.1278_general"   # London
    
    # Debug graph connectivity
    shortest_path = nx.shortest_path(G, start_node, goal_node) if nx.has_path(G, start_node, goal_node) else None
    logger.info(f"Shortest path from {start_node} to {goal_node}: {shortest_path}")

    # Train PPO
    ppo_model = train_ppo_agent(G, start_node, goal_node, timesteps=100000)
    ppo_env = RouteEnv(G, start_node, goal_node)
    ppo_env.w1, ppo_env.w2, ppo_env.w3 = 0.2, 0.2, 0.6
    ppo_paths = evaluate_agent(ppo_model, ppo_env)
    logger.info("PPO Paths:")
    for i, path in enumerate(ppo_paths):
        logger.info(f"Path {i + 1}: {' -> '.join(path)}")

if __name__ == "__main__":
    main()