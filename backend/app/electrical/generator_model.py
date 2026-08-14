"""
Electromagnetic model of the direct-drive PM synchronous generator/
alternator (Stage 11 -- additive, doesn't touch any existing Stage 1-10
behaviour).

Two distinct things are modelled here, matching what a real machine
datasheet describes:

1. `generator_operating_point` -- couples the generator to whatever
   mechanical torque/speed the rotor's BEM solver actually delivers at a
   given wind speed/TSR (Stage 1 output). This assumes the power
   electronics load the generator such that its electromagnetic torque
   matches the rotor's available mechanical torque at that point (i.e. the
   generator absorbs everything the aero model says is available) and
   reports the resulting electrical output net of copper + core losses.

2. `torque_speed_curve` -- the generator's own intrinsic characteristic
   independent of any particular rotor: for a fixed reflected load
   resistance behind the rectifier, how torque/current/power/efficiency
   vary with shaft speed. This is the curve you'd compare against a
   datasheet or use to pick a generator for a given rotor.

Equivalent-circuit convention (documented, not hidden): this is a lumped
single-equivalent-circuit model, the same simplification used on most small
BLDC/PMSG alternator datasheets -- torque constant Kt [Nm/A] and back-EMF
constant Ke [V per mechanical rad/s] are treated as whole-machine constants
with Kt = Ke by default (the standard identity for an ideal PM machine),
and `phase_current_a` / `phase_resistance_ohm` represent the single
equivalent current/impedance seen by the rectified DC-link, not a
per-phase decomposition. This keeps the model energy-consistent by
construction: P_mech = T*omega = Ke*omega*I = E*I always, and for the
load-matched curve, electromagnetic torque is *derived* from the real
power balance (P_elec + P_copper + P_core), never assumed independently --
that decoupling was an earlier bug (torque computed as Kt*I while power was
computed separately from the load circuit could disagree and imply
efficiency > 100%). No magnetic saturation, temperature-dependent
resistance, or harmonic content beyond the explicit cogging-torque
estimate below.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import gcd, pi

from app.geometry.models import GeneratorGeometry


@dataclass
class GeneratorOperatingPoint:
    omega_mech_rad_s: float
    rpm: float
    electrical_freq_hz: float
    mechanical_torque_nm: float
    mechanical_power_w: float
    phase_current_a: float
    back_emf_v: float
    terminal_voltage_v: float
    copper_loss_w: float
    core_loss_w: float
    electrical_power_w: float
    efficiency: float


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b) if a and b else 0


def cogging_ripple_frequency_hz(gen: GeneratorGeometry, rpm: float) -> float:
    """
    Cogging torque repeats `LCM(slots, 2*pole_pairs)` times per mechanical
    revolution -- the standard result for a slotted PM machine. Useful for
    knowing whether cogging ripple could excite a structural mode (see the
    Stage 9 aeroelastic Campbell diagram).
    """
    periods_per_rev = _lcm(gen.slot_count, 2 * gen.pole_pairs)
    return periods_per_rev * (rpm / 60.0)


def generator_operating_point(
    gen: GeneratorGeometry, mechanical_torque_nm: float, omega_mech_rad_s: float,
) -> GeneratorOperatingPoint:
    """
    Electrical response of the generator when the rotor delivers
    `mechanical_torque_nm` at shaft speed `omega_mech_rad_s` (i.e. the
    rotor's BEM operating point), assuming the generator's electromagnetic
    torque is loaded to match it exactly.
    """
    omega = max(omega_mech_rad_s, 0.0)
    T_mech = max(mechanical_torque_nm, 0.0)
    P_mech = T_mech * omega

    I = T_mech / gen.torque_constant_nm_per_a if gen.torque_constant_nm_per_a > 1e-9 else 0.0
    E = gen.k_e * omega
    Xs = gen.synchronous_reactance_ohm
    reactive_drop_sq = max(E ** 2 - (I * Xs) ** 2, 0.0)
    V_terminal = max(reactive_drop_sq ** 0.5 - I * gen.phase_resistance_ohm, 0.0)

    P_cu = I ** 2 * gen.phase_resistance_ohm
    P_core = gen.core_loss_coefficient * omega ** 1.5
    P_elec = max(P_mech - P_cu - P_core, 0.0)
    efficiency = P_elec / P_mech if P_mech > 1e-9 else 0.0

    rpm = omega * 60.0 / (2 * pi)
    f_elec = gen.pole_pairs * rpm / 60.0

    return GeneratorOperatingPoint(
        omega_mech_rad_s=omega, rpm=rpm, electrical_freq_hz=f_elec,
        mechanical_torque_nm=T_mech, mechanical_power_w=P_mech,
        phase_current_a=I, back_emf_v=E, terminal_voltage_v=V_terminal,
        copper_loss_w=P_cu, core_loss_w=P_core, electrical_power_w=P_elec,
        efficiency=efficiency,
    )


def torque_speed_curve(
    gen: GeneratorGeometry, rpm_max: float = 600.0, n_points: int = 30,
) -> list[GeneratorOperatingPoint]:
    """
    Intrinsic generator characteristic for a fixed reflected load
    resistance (`gen.load_resistance_ohm`), independent of any rotor --
    what you'd measure on a dyno or read off a datasheet: sweep shaft
    speed, solve the load circuit for current, and derive electromagnetic
    torque *from the resulting real power balance* (not from Kt*I
    independently) so efficiency can never exceed 100% by construction.
    """
    points = []
    Rs, Xs, Rl = gen.phase_resistance_ohm, gen.synchronous_reactance_ohm, gen.load_resistance_ohm
    Z = ((Rs + Rl) ** 2 + Xs ** 2) ** 0.5
    n = max(2, int(n_points))
    for i in range(n):
        rpm = rpm_max * (i + 1) / n
        omega = rpm * 2 * pi / 60.0
        E = gen.k_e * omega
        I = E / Z if Z > 1e-9 else 0.0

        # Real power delivered by the EMF source into the series R-X-R
        # circuit -- exact for a linear series circuit (the reactance
        # dissipates nothing), so this is energy-consistent by construction.
        P_elec = I ** 2 * Rl
        P_cu = I ** 2 * Rs
        P_core = gen.core_loss_coefficient * omega ** 1.5
        P_mech = P_elec + P_cu + P_core
        T_em = P_mech / omega if omega > 1e-9 else 0.0
        efficiency = P_elec / P_mech if P_mech > 1e-9 else 0.0

        f_elec = gen.pole_pairs * rpm / 60.0
        points.append(GeneratorOperatingPoint(
            omega_mech_rad_s=omega, rpm=rpm, electrical_freq_hz=f_elec,
            mechanical_torque_nm=T_em, mechanical_power_w=P_mech,
            phase_current_a=I, back_emf_v=E, terminal_voltage_v=max(E - I * Rs, 0.0),
            copper_loss_w=P_cu, core_loss_w=P_core, electrical_power_w=P_elec,
            efficiency=efficiency,
        ))
    return points


@dataclass
class BreakawayCheck:
    cogging_torque_peak_nm: float
    rotor_starting_torque_nm: float
    can_break_away: bool
    margin_nm: float


def check_breakaway(gen: GeneratorGeometry, rotor_starting_torque_nm: float) -> BreakawayCheck:
    """
    Compares the rotor's low-TSR (near-standstill) aerodynamic torque
    against the generator's peak cogging (detent) torque. If cogging wins,
    the rotor can't break away from rest at that wind speed no matter what
    the BEM power curve predicts once spinning.
    """
    margin = rotor_starting_torque_nm - gen.cogging_torque_peak_nm
    return BreakawayCheck(
        cogging_torque_peak_nm=gen.cogging_torque_peak_nm,
        rotor_starting_torque_nm=rotor_starting_torque_nm,
        can_break_away=margin > 0,
        margin_nm=margin,
    )