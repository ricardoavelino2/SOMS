import numpy as np
from typing import Union

Array1D = Union[np.ndarray, float]


def P_delta(Pr: Array1D,
            I: Array1D,
            Lb: Array1D,
            E: float = 29000,
            tao_b: float = 1.0,
            Cm: Array1D = 1.0,
            alpha: float = 1.0) -> Array1D:
    r"""
    Calculate the B1 multiplier for :math:`P-\delta` effects using AISC
    Appendix 8 (Approximate Second-Order Analysis), with respect to the
    provided axis.

    Parameters
    ----------
    Pr : Array1D
        Required axial strength .
    I : Array1D
        Moment of intertia about the chosen axis (in^4 or mm^4).
    Lb : Array1D
        Member unbraced length (in. or mm).
    E : float, optional
        Modulus of elasticity of steel. 29000 ksi (200,000 MPa)
    tao_b : float, optional
        Stiffness reduction parameter, see Chapter C. The default is 1.0.
    Cm : Array1D, optional
        Coefficient accounting for nonuniform moment. The default is 1.0.
    alpha : float, optional
        alpha = 1.0 (LRFD), or 1.6 (ASD). The default is 1.0.

    Returns
    -------
    Array1D
        Multiplier for :math:`P-\delta` effects B1.

    """

    # TODO: tao_b is assumed to be 1, implement Chapter C3
    # Do all forces have the same sign? (we don't want to handle edge cases)
    assert np.all(Pr > 0) if Pr[0] > 0 else np.all(Pr < 0), \
        "Not all forces have the same sign, are some columns in tension?"
    Pr = np.abs(Pr)

    # Elastic critical buckling strength (AISC A-8-5)
    Pe1 = np.pi**2 * 0.8 * tao_b * E * I / (Lb)**2

    # AISC Appendix 8, (AISC A-8-3)
    B1 = Cm / (1 - alpha * Pr/Pe1)
    return B1


def E3_compression(A: Array1D,
                   rx: Array1D,
                   ry: Array1D,
                   Lb: Array1D,
                   Fy: Array1D,
                   E: float = 29000) -> Array1D:
    r"""
    AISC Chapter E Design of Members for Compression (E3)

    Parameters
    ----------
    A : Array1D
        Member areas.
    rx : Array1D
        Radius of gyration wrt strong axis.
    ry : Array1D
        Radius of gyration wrt weak axis.
    Lb : Union[Array1D, float]
        Member unbraced length, in.
    Fy : Union[Array1D, float]
        Yield strength, ksi.
    E : float, optional
        Young's modulus, ksi. The default is 29000

    Returns
    -------
    Array1D
        Compression capacity, :math:`\phi P_n`, (kip).

    """

    # Elastic buckling stress (AISC E3-4)
    r_min = np.minimum(rx, ry)
    Fe = np.pi**2 * E / (Lb / r_min)**2

    # Critical stress, (AISC E3-2, E3-3)
    Fcr = np.where(Fy / Fe <= 2.25,
                   0.658**(Fy / Fe) * Fy,  # Inelastic
                   0.877 * Fe)  # Elastic

    phiPn = 0.9*Fcr*A
    return phiPn


def F2_flexure_major(Lb: Array1D,
                     Fy: Array1D,
                     section_type: Union[Array1D, None] = None,
                     ho: Union[Array1D, None] = None,
                     J: Union[Array1D, None] = None,
                     Sx: Union[Array1D, None] = None,
                     Zx: Union[Array1D, None] = None,
                     ry: Union[Array1D, None] = None,
                     rts: Union[Array1D, None] = None,
                     Iy: Union[Array1D, None] = None,
                     Cw: Union[Array1D, None] = None,
                     props: Union[dict, None] = None,
                     Cb: Array1D = 1.0,
                     E: float = 29000) -> Array1D:
    r"""
    AISC Chapter F Design of Members for Flexure (F2)

    Parameters
    ----------
    Lb : Union[Array1D, float]
        Length between points that are either braced against lateral
        displacement fo compression flange or braced against twist of the cross
        section (in. or mm).
    Fy : Union[Array1D, float]
        Specified minimum yield strength (ksi or MPa).
    section_type : Union[Array1D, None]
        String indicating section type ('W' or 'C')
    ho : Union[Array1D, None]
        Distance between flange centroids (in. or mm).
    J : Union[Array1D, None]
        Torsional constant (in^4 or mm^4).
    Sx : Union[Array1D, None]
        Elastic section modulus taken about the :math:`x`-axis,
        :math:`in^3 (mm^3)`.
    Zx : Union[Array1D, None]
        Plastic section modulus taken about the :math:`x`-axis,
        :math:`in^3 (mm^3)`.
    ry : Union[Array1D, None]
        Radius of gyration about the y-axis (in. or mm).
    rts : Union[Array1D, None]
        Effective radius of gyration (in. or mm).
    Iy : Union[Array1D, None]
        Moment of intertia about the channel weak axis, for channels only
        (in^4 or mm^4).
    Cw : Union[Array1D, None]
        Warping constant (in^6 or mm^6).
    props : Union[dict, None], optional
        Optionally pass in section properties in a dict or DataFrame.
        The default is None.
    Cb : Union[Array1D, float], optional
        Lateral-torsional buckling modification factor for non-uniform moment
        diagrams. The default is 1.0.
    E : float, optional
        Modulus of elasticity of steel. 29000 ksi (200,000 MPa)

    Returns
    -------
    Array1D
        Strong axis moment capacity, :math:`\phi M_{n_x}`, (kip-in, N-mm)

    """

    if props is not None:
        section = props['Type']
        ho = props['ho'].astype('float64')
        J = props['J'].astype('float64')
        Sx = props['Sx'].astype('float64')
        Zx = props['Zx'].astype('float64')
        ry = props['ry'].astype('float64')
        rts = props['rts'].astype('float64')
        # only used for channels
        if np.any(section == 'C'):
            Iy = props['Iy'].astype('float64')
            Cw = props['Cw'].astype('float64')
        else:
            Iy = 0.0
            Cw = 1.0

    # AISC F2-8
    assert np.all((section == 'W') | (section == 'C')), \
        """section_type array contains elements other than 'W' or 'C'.
        F2 is only defined for W or C shapes"""
    c = np.where(section == "W", 1, ho / 2 * np.sqrt(Iy/Cw))

    # Plastic moment (AISC F2-1)
    Mp = Fy * Zx

    # Limiting laterally unbraced length for the limit state of yielding,
    # (AISC F2-5)
    Lp = 1.76 * ry * np.sqrt(E / Fy)

    # Limiting laterally unbraced length for the limit state of inelastic
    # lateral-torsional buckling, (AISC F2-6)
    Lr = 1.95 * rts * E / (0.7 * Fy) * np.sqrt(J * c / (Sx * ho) +
                                               np.sqrt((J * c / (Sx * ho))**2 +
                                                       6.76*(0.7 * Fy / E)**2)
                                               )

    # Elastic lateral-torsional buckling moment (AISC F2-3, F2-4)
    Mn_elastic = Cb*np.pi**2*E / (Lb/rts)**2 *\
        np.sqrt(1 + 0.078*(J*c)/(Sx*ho) * (Lb/rts)**2) * Sx

    # Inelastic lateral-torsional buckling moment (AISC F2-2)
    Mn_inelastic = Cb*(Mp - (Mp - 0.7*Fy*Sx) * (Lb - Lp)/(Lr - Lp))

    # Nominal flexural strength
    Mn = np.where(Lb <= Lp,
                  Mp,
                  np.where(Lb > Lr,
                           np.minimum(Mp, Mn_elastic),
                           np.minimum(Mp, Mn_inelastic)
                           )
                  )

    phiMnx = 0.9 * Mn
    return phiMnx


def F6_flexure_minor(Sy: Array1D,
                     Zy: Array1D,
                     lambda_f: Array1D,
                     Fy: Array1D,
                     E: float = 29000) -> Array1D:
    r"""
    AISC Chapter F Design of Members for Flexure (F6)

    Parameters
    ----------
    Sy : Array1D
        Elastic section modulus taken about the :math:`y`-axis,
        :math:`in^3 (mm^3)`.
    Zy : Array1D
        Plastic section modulus taken about the :math:`y`-axis,
        :math:`in^3 (mm^3)`.
    lambda_f : Array1D
        Slenderness parameter, equal to :math:`\frac{b_f}{2 t_f` for I-shapes,
                                                          see AISC F6-4.
    Fy : Array1D
        Specified minimum yield strength (ksi or MPa).
    E : float, optional
        Modulus of elasticity of steel. 29000 ksi (200,000 MPa)

    Returns
    -------
    Array1D
        Weak axis moment capacity, :math:`\phi M_{n_y}`, (kip-in, N-mm).

    """

    # Width-to-thickness ratios: AISC TABLE B4.1b Case 10
    # Limiting ratio for compact/noncompact section
    lambda_pf = 0.38 * np.sqrt(E / Fy)

    # Limiting ratio for noncompact/slender section
    lambda_rf = np.sqrt(E / Fy)

    # Plastic moment (AISC F6-1)
    Mp = np.minimum(Fy*Zy, 1.6*Fy*Sy)

    # Flange Local Buckling
    is_compact = lambda_f <= lambda_pf
    is_slender = lambda_f >= lambda_rf

    # Elastic flange local buckling moment (AISC F6-3, F6-4)
    Mn_elastic = (0.69*E*Sy) / lambda_f**2

    # Nominal flexural strength
    # For non-compact flanges, interpolate between Mp and reduced moment
    Mn = np.where(is_compact,
                  Mp,
                  np.where(is_slender,
                           Mn_elastic,
                           Mp - (Mp - 0.7 * Fy * Sy) *
                           (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)
                           )
                  )

    phiMny = 0.9*Mn
    return phiMny


def F8_flexure_round_hss(D: Array1D,
                         t: Array1D,
                         S: Array1D,
                         Z: Array1D,
                         Fy: Array1D,
                         E: float = 29000) -> Array1D:
    r"""
    Flexural capacity of round HSS members following AISC section F8.

    Parameters
    ----------
    D : Array1D
        Outside diameter of round HSS, (in. or mm)
    t : Array1D
        Design wall thickness of memmber (see Spec. Commentary Section B4.2).
        (in. or mm)
    S : Array1D
        Elastic section modulus, :math:`in^3 (mm^3)`.
    Z : Array1D
        Plastic section modulus, :math:`in^3 (mm^3)`.
    Fy : Union[Array1D, float]
        Specified minimum yield strength (ksi or MPa).
    E : float, optional
        Modulus of elasticity of steel. 29000 ksi (200,000 MPa)

    Returns
    -------
    Array1D
        Section moment capacity, :math:`\phi M_n`, (kip-in, N-mm).

    """

    assert np.all(D/t < 0.45*E/Fy), "F8 does not apply if D/t > 0.45 E/Fy"

    # Yielding (AISC F8-1)
    Mp = Fy*Z

    # Local buckling
    lambda_p = 0.07 * E/Fy  # Limiting ratio for compact/noncompact section
    lambda_r = 0.31 * E/Fy  # Limiting ratio for noncompact/slender section

    is_slender = D/t >= lambda_r
    is_compact = D/t < lambda_p

    # Noncompact sections
    Mn_noncompact = (0.021*E/(D/t) + Fy) * S

    # Slender sections
    Fcr = 0.33*E/(D/t)
    Mn_slender = Fcr * S

    Mn = np.where(is_compact,
                  Mp,
                  np.where(is_slender,
                           np.minimum(Mp, Mn_slender),
                           np.minimum(Mp, Mn_noncompact)
                           )
                  )
    phiMn = 0.9*Mn
    return phiMn


def F9_flexure_t_2l(shape: Union[Array1D, str],
                    stem_tension: Union[Array1D, bool],
                    d: Array1D,
                    tw: Array1D,
                    Sx: Array1D,
                    Zx: Array1D,
                    J: Array1D,
                    Iy: Array1D,
                    y: Array1D,
                    lambda_f: Array1D,  # bf/2tf
                    Lb: Array1D,
                    Fy: Array1D,
                    E: float = 29000,
                    G: float = 11200) -> Array1D:
    """
    Flexural capacity of Tee sections and double angles following AISC section
    F9.

    Parameters
    ----------
    shape : Union[Array1D, str]
        DESCRIPTION.
    stem_tension : Union[Array1D, bool]
        DESCRIPTION.
    d : Array1D
        DESCRIPTION.
    tw : Array1D
        DESCRIPTION.
    Sx : Array1D
        Elastic section modulus taken about the :math:`x`-axis,
        :math:`in^3 (mm^3)`.
    Zx : Array1D
        Plastic section modulus taken about the :math:`x`-axis,
        :math:`in^3 (mm^3)`.
    J : Array1D
        Torsional constant (in^4 or mm^4).
    Iy : Array1D
        Moment of intertia about the weak axis (in^4 or mm^4).
    y : Array1D
        DESCRIPTION.
    lambda_f : Array1D
        DESCRIPTION.# bf/2tf
    Lb : Array1D
        DESCRIPTION.
    Fy : Array1D
        DESCRIPTION.
    E : float, optional
        DESCRIPTION. The default is 29000.
    G : float, optional
        DESCRIPTION. The default is 11200.

    Returns
    -------
    Array1D
        DESCRIPTION.

    """
    import warnings
    warnings.warn("F9 provisions might not be correctly implemented.",
                  UserWarning)

    # TODO: which provision apply to double angles, which to T's?
    # maybe this needs to be two functions?
    # TODO: test behavior - how is tension boolean handled?

    # 1. Yielding (AISC F9-2, F9-3)
    Mp = np.where(stem_tension,
                  np.minimum(Fy*Zx, 1.6*Fy*Sx),
                  np.minimum(Fy*Zx, Fy*Sx)
                  )

    # 2. Lateral-torsional Buckling (AISC F9-4)
    B = np.where(stem_tension, 1, -1) * 2.3 * (d / Lb) * np.sqrt(Iy / J)
    Mcr = np.pi * np.sqrt(E * Iy * G * J)/Lb * (B + np.sqrt(1 + B**2))

    # 3. Flange Local Buckling of Tees #
    # This assumes flanges in flexural compression (stem in tension)

    # TODO verify correct case
    # Width-to-thickness ratios: AISC TABLE B4.1b Case 10
    # Limiting ratio for compact/noncompact section
    lambda_pf = 0.38 * np.sqrt(E / Fy)

    # Limiting ratio for noncompact/slender section
    lambda_rf = np.sqrt(E / Fy)

    is_compact = lambda_f <= lambda_pf
    is_slender = lambda_f >= lambda_rf

    # Nominal flexural strength
    S_xc = Iy / y  # elastic section modulus referred to the compression flange
    Mn_flb = np.where(is_compact,
                      np.inf,  # flange local buckling does not apply
                      np.where(is_slender,
                               0.7 * E * S_xc / lambda_f**2,
                               np.minimum(Mp - (Mp - 0.7*Fy*S_xc) *\
                                          (lambda_f - lambda_pf) /\
                                          (lambda_rf - lambda_pf),
                                          1.6 * Fy * Sx)
                               )
                      )

    # 4. Local Buckling of Tee Stems in Flexural Compression
    d_div_tw = d/tw
    Fcr = np.where(d_div_tw <= 0.84 * np.sqrt(E/Fy),
                   Fy,
                   np.where(d_div_tw <= 1.03 * np.sqrt(E/Fy),
                            Fy*(2.55 - 1.84 * d_div_tw * np.sqrt(Fy/E)),
                            0.69*E/d_div_tw**2)
                   )
    Mn_slb = Fcr * Sx

    # Clauses 1 & 2
    Mn_tension = np.minimum(Mp, Mcr)

    # Clauses 3 & 4
    # TODO: fix logic. do we need to return different phiMn for each axis?
    Mn_lb = np.minimum(Mn_flb,
                       np.where(stem_tension,
                                np.inf,
                                Mn_slb)
                       )

    phiMn = 0.9*np.minimum(Mn_tension, Mn_lb)
    return phiMn


def H1_interaction(Pr: Array1D,
                   Pc: Array1D,
                   Mrx: Array1D,
                   Mcx: Array1D,
                   Mry: Array1D,
                   Mcy: Array1D) -> Array1D:
    """
    AISC Chapter H Design of Members for Combined Forces and Torsion (H1)

    Parameters
    ----------
    Pr : Array1D
        Required axial strength (kips, N).
    Pc : Array1D
        Available axial strength, see Chapter E, (kips, N).
    Mrx : Array1D
        Required strong axis flexural strength (kip-in, N-mm).
    Mcx : Array1D
        Available strong axis flexural strength, see Chapter F, (kip-in, N-mm).
    Mry : Array1D
        Required weak axis flexural strength (kip-in, N-mm).
    Mcy : Array1D
        Available weak axis flexural strength, see Chapter F, (kip-in, N-mm).

    Returns
    -------
    Array1D
        Interaction ratio.

    """

    assert np.all(Pr > 0) if Pr[0] > 0 else np.all(Pr < 0), \
        "Not all forces have the same sign, are some columns in tension?"
    Pr = np.abs(Pr)

    M_total_int = np.abs(Mrx)/Mcx + np.abs(Mry)/Mcy

    # AISC H1
    DCR = np.where(Pr/Pc >= 0.2,
                   Pr/Pc + 8/9 * M_total_int,
                   Pr/Pc/2 + M_total_int
                   )

    return DCR
