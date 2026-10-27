package com.cameramonitoring.app

import com.cameramonitoring.app.data.model.*
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class VisionRulesContractTest {
    @Test fun scopeFromServerIsNeverSubmittedBack() {
        val gson = Gson()
        val json = """{"revision":7,"can_manage":false,"rules":[{"rule_id":"r1","kind":"intrusion","enabled":false,"owner_id":"private","organization_id":"private-org","camera_id":"camera","classes":["person"],"polygon":[{"x":0.1,"y":0.1},{"x":0.9,"y":0.1},{"x":0.5,"y":0.9}],"direction":"both","threshold":1,"min_confidence":0.8,"min_observations":3,"line_margin":0.01,"duration_seconds":10,"cooldown_seconds":30,"stationary_radius":0.02,"timezone_name":"UTC","weekdays":[0,1],"start":"08:00:00","end":"18:00:00"}]}"""
        val config = gson.fromJson(json, VisionConfig::class.java)
        assertFalse(config.canManage)
        assertEquals(7L, config.revision)
        assertEquals(3, config.rules[0].minObservations)
        val request = gson.toJson(VisionConfigUpdate(config.revision, config.rules))
        assertFalse(request.contains("owner_id"))
        assertFalse(request.contains("organization_id"))
        assertFalse(request.contains("camera_id"))
        assertTrue(request.contains("min_confidence"))
    }

    @Test fun newRuleRequiresExplicitEnable() {
        val rule = VisionRule("new")
        assertFalse(rule.enabled)
        assertEquals(2, rule.minObservations)
    }
}
