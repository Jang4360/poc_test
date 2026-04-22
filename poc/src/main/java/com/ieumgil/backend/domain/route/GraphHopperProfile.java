package com.ieumgil.backend.domain.route;

public enum GraphHopperProfile {
	VISUAL_SAFE("visual_safe"),
	VISUAL_FAST("visual_fast"),
	WHEELCHAIR_SAFE("wheelchair_safe"),
	WHEELCHAIR_FAST("wheelchair_fast");

	private final String profileName;

	GraphHopperProfile(String profileName) {
		this.profileName = profileName;
	}

	public String profileName() {
		return profileName;
	}

	public static GraphHopperProfile from(DisabilityType disabilityType, RouteOption routeOption) {
		return switch (routeOption) {
			case SAFE -> disabilityType == DisabilityType.VISUAL ? VISUAL_SAFE : WHEELCHAIR_SAFE;
			case SHORTEST -> disabilityType == DisabilityType.VISUAL ? VISUAL_FAST : WHEELCHAIR_FAST;
			case PUBLIC_TRANSPORT -> throw new IllegalArgumentException(
				"PUBLIC_TRANSPORT is orchestrated separately and does not map to a direct GraphHopper profile."
			);
		};
	}
}
