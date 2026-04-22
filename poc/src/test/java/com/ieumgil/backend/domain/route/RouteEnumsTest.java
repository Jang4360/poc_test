package com.ieumgil.backend.domain.route;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Test;

class RouteEnumsTest {

	@Test
	void disabilityTypeMatchesPlan01Contract() {
		assertEquals(List.of("VISUAL", "MOBILITY"), enumNames(DisabilityType.values()));
	}

	@Test
	void routeOptionMatchesPlan01Contract() {
		assertEquals(List.of("SAFE", "SHORTEST", "PUBLIC_TRANSPORT"), enumNames(RouteOption.values()));
	}

	@Test
	void graphHopperProfilesFollowPlan01Mapping() {
		assertEquals(GraphHopperProfile.VISUAL_SAFE, GraphHopperProfile.from(DisabilityType.VISUAL, RouteOption.SAFE));
		assertEquals(GraphHopperProfile.VISUAL_FAST, GraphHopperProfile.from(DisabilityType.VISUAL, RouteOption.SHORTEST));
		assertEquals(GraphHopperProfile.WHEELCHAIR_SAFE, GraphHopperProfile.from(DisabilityType.MOBILITY, RouteOption.SAFE));
		assertEquals(GraphHopperProfile.WHEELCHAIR_FAST, GraphHopperProfile.from(DisabilityType.MOBILITY, RouteOption.SHORTEST));
		assertEquals("wheelchair_safe", GraphHopperProfile.WHEELCHAIR_SAFE.profileName());
	}

	@Test
	void publicTransportDoesNotMapToDirectGraphHopperProfile() {
		assertThrows(
			IllegalArgumentException.class,
			() -> GraphHopperProfile.from(DisabilityType.MOBILITY, RouteOption.PUBLIC_TRANSPORT)
		);
	}

	private static List<String> enumNames(Enum<?>[] values) {
		return List.of(values).stream()
			.map(Enum::name)
			.toList();
	}
}
