"""FastAPI HTTP layer: request/response handling and orchestration only.

All physics lives in other modules:

* divider.py     -> open-circuit divider difference
* thevenin.py    -> loaded galvanometer reading
* balance.py     -> closed-form solve for the unknown arm
* registry.py    -> named bridge presets
* validation.py  -> pre-computation validation with reasons

There is intentionally no web UI; this service is JSON over HTTP only.
"""
from __future__ import annotations

from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse

from . import balance, divider, thevenin, validation
from .registry import ConfigNotFoundError, registry
from .schemas import (
    ConfigListResponse,
    ConfigRegisterRequest,
    ConfigResponse,
    ErrorResponse,
    GalvanometerResult,
    OutputRequest,
    OutputResponse,
    SolveRequest,
    SolveResponse,
)

app = FastAPI(
    title="Wheatstone Bridge Calculator",
    version="1.0.0",
    description=(
        "Resident Wheatstone-bridge calculation service: unbalanced open-circuit "
        "output, galvanometer-loaded deflection (Thevenin), and closed-form "
        "balance solve of the unknown arm. JSON over HTTP only."
    ),
)


@app.exception_handler(validation.BridgeValidationError)
async def handle_validation_error(_request, exc: validation.BridgeValidationError):
    """Input rejected before computation: 400 with an explicit reason."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error="invalid_input", reason=str(exc)).model_dump(),
    )


@app.exception_handler(ConfigNotFoundError)
async def handle_config_not_found(_request, exc: ConfigNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(error="config_not_found", reason=str(exc)).model_dump(),
    )


def _resolve_arms(request: OutputRequest) -> dict[str, float]:
    """Pick arms from either the explicit payload or a registered preset."""
    if (request.arms is None) == (request.config is None):
        raise validation.BridgeValidationError(
            "provide exactly one of 'arms' (explicit r1..r4) or 'config' "
            "(name of a registered bridge preset), not both and not neither"
        )
    if request.arms is not None:
        return validation.validate_arms(request.arms)
    return registry.get(request.config).arms()


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/bridge/output",
    response_model=OutputResponse,
    tags=["bridge"],
    summary="Forward calculation: unbalanced output and optional galvanometer reading",
)
def bridge_output(request: OutputRequest) -> OutputResponse:
    arms = _resolve_arms(request)
    source_voltage = validation.validate_source_voltage(request.source_voltage)
    r_g = (
        validation.validate_galvanometer_resistance(
            request.galvanometer_resistance
        )
        if request.galvanometer_resistance is not None
        else None
    )

    balanced = balance.is_balanced(**arms)
    r_th = thevenin.thevenin_resistance(**arms)

    # Zero source voltage is a valid operating point, not an error: the output
    # is zero by definition. Return it directly and flag it in the note.
    if source_voltage == 0.0:
        return OutputResponse(
            arms=arms,
            source_voltage=source_voltage,
            balanced=balanced,
            open_circuit_voltage=0.0,
            branch_potentials={"b": 0.0, "d": 0.0},
            thevenin_resistance=r_th,
            galvanometer=GalvanometerResult(
                thevenin_voltage=0.0,
                thevenin_resistance=r_th,
                galvanometer_resistance=r_g,
                current=0.0,
                terminal_voltage=0.0,
            )
            if r_g is not None
            else None,
            note=(
                "source_voltage is zero; by Ohm/divider relations the bridge "
                "output is identically zero (flagged, not treated as an error)"
            ),
        )

    open_voltage = divider.open_circuit_voltage(
        **arms, source_voltage=source_voltage
    )
    v_b = divider.branch_potential(arms["r1"], arms["r4"], source_voltage)
    v_d = divider.branch_potential(arms["r2"], arms["r3"], source_voltage)

    galvanometer_result = None
    if r_g is not None:
        reading = thevenin.galvanometer_reading(
            **arms,
            source_voltage=source_voltage,
            galvanometer_resistance=r_g,
        )
        galvanometer_result = GalvanometerResult(
            thevenin_voltage=reading.thevenin_voltage,
            thevenin_resistance=reading.thevenin_resistance,
            galvanometer_resistance=reading.galvanometer_resistance,
            current=reading.current,
            terminal_voltage=reading.terminal_voltage,
        )

    note = None
    if balanced:
        note = "bridge is balanced: opposite-arm products r1*r3 and r2*r4 are equal"

    return OutputResponse(
        arms=arms,
        source_voltage=source_voltage,
        balanced=balanced,
        open_circuit_voltage=open_voltage,
        branch_potentials={"b": v_b, "d": v_d},
        thevenin_resistance=r_th,
        galvanometer=galvanometer_result,
        note=note,
    )


@app.post(
    "/bridge/solve",
    response_model=SolveResponse,
    tags=["bridge"],
    summary="Inverse calculation: solve the unknown arm required for balance",
)
def bridge_solve(request: SolveRequest) -> SolveResponse:
    known = validation.validate_known_arms(request.known_arms)
    unknown_arm, value = balance.solve_unknown_arm(known)
    completed = {**known, unknown_arm: value}
    residual = balance.balance_residual(**completed)
    return SolveResponse(
        unknown_arm=unknown_arm,
        resistance=value,
        known_arms=known,
        formula=balance.FORMULA[unknown_arm],
        balance_residual=residual,
        note=(
            "closed-form solve from the balance condition r1*r3 = r2*r4 "
            "(products of OPPOSITE arms equal)"
        ),
    )


@app.post(
    "/configs",
    response_model=ConfigResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["presets"],
    summary="Register (or replace) a named four-arm bridge preset",
)
def register_config(request: ConfigRegisterRequest) -> ConfigResponse:
    config = registry.register(request.name, request.arms)
    return ConfigResponse(name=config.name, arms=config.arms())


@app.get("/configs", response_model=ConfigListResponse, tags=["presets"])
def list_configs() -> ConfigListResponse:
    return ConfigListResponse(
        configs=[ConfigResponse(name=c.name, arms=c.arms()) for c in registry.list()]
    )


@app.get("/configs/{name}", response_model=ConfigResponse, tags=["presets"])
def get_config(name: str) -> ConfigResponse:
    config = registry.get(name)
    return ConfigResponse(name=config.name, arms=config.arms())


@app.delete(
    "/configs/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["presets"],
    response_class=Response,
)
def delete_config(name: str) -> Response:
    registry.delete(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
