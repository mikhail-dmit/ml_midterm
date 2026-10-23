"""Inference-only role allocation, history switching and two-stage reranking."""

from hybrid_models import reciprocal_rank_fusion


def allocate_slots(familiar, new, familiar_slots, k=5):
    if not 0 <= familiar_slots <= k:
        raise ValueError("Invalid familiar-slot budget")
    if len(set(familiar)) != len(familiar) or len(set(new)) != len(new) or set(familiar) & set(new):
        raise ValueError("Role queues must be distinct and disjoint")
    chosen, roles = [], []
    queues = {"familiar": list(familiar), "new": list(new)}
    for requested in ["familiar"]*familiar_slots + ["new"]*(k-familiar_slots):
        actual = requested if queues[requested] else ("new" if requested == "familiar" else "familiar")
        if not queues[actual]:
            raise ValueError("Role queues cannot fill the output")
        chosen.append(queues[actual].pop(0))
        roles.append(actual)
    return chosen, roles


def rerank_candidates(candidates, score, k=5):
    if len(set(candidates)) != len(candidates) or len(candidates) < k:
        raise ValueError("Insufficient distinct rerank candidates")
    positions = {item: rank for rank, item in enumerate(candidates)}
    return sorted(candidates, key=lambda item: (-score(item), positions[item]))[:k]


def predict_user(config, queues, score, history_size, cold, popularity):
    """Queues/score/history are all training-derived; labels are not accepted."""
    if cold:
        return popularity[:5], ["cold_popularity"]*5
    if "max_sparse_history" in config and history_size <= config["max_sparse_history"]:
        return popularity[:5], ["sparse_popularity"]*5
    if config["type"] == "single":
        return queues[config["method"]]["global"][:5], [config["method"]]*5
    if config["type"] == "switch":
        method = config["warm_method"]
        return queues[method]["global"][:5], [method]*5
    if config["type"] == "slots":
        familiar = queues[config["favourite"]]["familiar"]
        new = queues[config["new"]]["new"]
        if "new_reranker" in config:
            candidates = new[:config["depth"]]
            new = rerank_candidates(candidates, lambda item: score(config["new_reranker"], item), k=len(candidates))
        return allocate_slots(familiar, new, config["familiar_slots"])
    if config["type"] == "rerank":
        candidates = queues[config["generator"]]["global"][:config["depth"]]
        chosen = rerank_candidates(candidates, lambda item: score(config["reranker"], item))
        return chosen, ["reranked"]*5
    if config["type"] == "rrf":
        lists = {m: queues[m]["global"][:5] for m in config["weights"]}
        pop_positions = {item: rank for rank, item in enumerate(popularity)}
        union = set(popularity[:5]).union(*lists.values())
        local_pop = sorted(union, key=pop_positions.__getitem__)
        chosen, _ = reciprocal_rank_fusion(lists, config["weights"], local_pop, config["offset"])
        return chosen, ["rrf_control"]*5
    raise ValueError(config["type"])
