from dataclasses import dataclass

from app.gateways.model_router import ModelConfig


@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    is_open: bool = False


class CircuitBreaker:
    def __init__(self):
        self._states: dict[str, CircuitBreakerState] = {}

    def is_open(self, key: str) -> bool:
        return self._get_state(key).is_open

    def get_state(self, key: str) -> CircuitBreakerState:
        return self._get_state(key)

    def record_success(self, key: str) -> None:
        self._states[key] = CircuitBreakerState()

    def record_failure(self, key: str, failure_threshold: int) -> None:
        if failure_threshold <= 0:
            return

        state = self._get_state(key)
        state.failure_count += 1

        if state.failure_count >= failure_threshold:
            state.is_open = True

    def reset(self) -> None:
        self._states.clear()

    def _get_state(self, key: str) -> CircuitBreakerState:
        if key not in self._states:
            self._states[key] = CircuitBreakerState()

        return self._states[key]


def model_circuit_key(model_config: ModelConfig) -> str:
    return f"{model_config.provider}:{model_config.model}"


circuit_breaker = CircuitBreaker()
