package com.cameramonitoring.app

import com.cameramonitoring.app.data.model.*
import com.cameramonitoring.app.data.remote.ApiService
import com.cameramonitoring.app.data.repository.EventRepository
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.async
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.CancellationException
import java.util.concurrent.TimeUnit
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class ProductReadinessContractTest {
    @Test fun partialAttentionNeverClaimsUnseenCamerasHaveZeroIncidents() {
        val data = CameraAttention(mapOf("camera" to 3L), complete = false)
        assertEquals(3L, data.pending("camera"))
        assertNull(data.pending("other"))
        assertEquals(0L, data.copy(complete = true).pending("other"))
    }

    @Test fun uncertainSignalsRemainHumanReviewAndDatesRespectOffsets() {
        val event = CameraEvent("event", "camera", eventType = "vision_probable_abandoned_object")
        assertTrue(event.incidentReason().contains("Posible"))
        assertTrue(event.copy(eventType = "unknown").incidentReason().contains("revisión humana"))
        assertEquals(eventTimestampLabel("2026-10-28T12:00:00Z"), eventTimestampLabel("2026-10-28T06:00:00-06:00"))
        assertEquals("Fecha no disponible", eventTimestampLabel(null))
    }

    @Test fun zoneFilterIsSentToBothHistoryAndStatistics() = runBlocking {
        val server = MockWebServer(); server.start()
        try {
            val api = Retrofit.Builder().baseUrl(server.url("/")).addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
            server.enqueue(MockResponse().setBody("""{"total":0,"events":[]}"""))
            api.getEvents(cameraId = "camera", ruleId = "rule")
            assertEquals("rule", server.takeRequest().requestUrl!!.queryParameter("rule_id"))
            server.enqueue(MockResponse().setBody("""{"total":0,"pending":0,"since":"a","until":"b","scope":"authorized_window"}"""))
            api.getEventStatistics(cameraId = "camera", ruleId = "rule")
            assertEquals("rule", server.takeRequest().requestUrl!!.queryParameter("rule_id"))
            server.enqueue(MockResponse().setBody("""{"pending_by_camera":{"camera":2},"complete":false}"""))
            val response = api.getCameraAttention().body()!!
            assertEquals(2L, response.pending("camera")); assertNull(response.pending("other"))
        } finally { server.shutdown() }
    }
    @Test fun requestedRuleFilterRequiresServerAcknowledgement() = runBlocking {
        val server = MockWebServer(); server.start()
        val rule = "00000000-0000-0000-0000-000000000010"
        try {
            val api = Retrofit.Builder().baseUrl(server.url("/")).addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
            val repository = EventRepository(api)
            server.enqueue(MockResponse().setBody("""{"total":0,"events":[]}"""))
            assertTrue(repository.getEventPage(ruleId = rule).isFailure)
            server.enqueue(MockResponse().setBody("""{"total":0,"events":[],"applied_filters":{"rule_id":"$rule"}}"""))
            assertTrue(repository.getEventPage(ruleId = rule).isSuccess)
            server.enqueue(MockResponse().setBody("""{"total":0,"pending":0,"since":"a","until":"b","scope":"authorized_window"}"""))
            assertNull(repository.getStatistics(null,null,null,null,rule))
        } finally { server.shutdown() }
    }

    @Test fun cancelledNetworkRequestDoesNotReturnAsAnOrdinaryFailure() = runBlocking {
        val server = MockWebServer(); server.start()
        try {
            server.enqueue(MockResponse().setHeadersDelay(1, TimeUnit.SECONDS).setBody("""{"total":0,"events":[]}"""))
            val api = Retrofit.Builder().baseUrl(server.url("/")).addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
            val repository = EventRepository(api)
            var returned = false
            val request = async(start = CoroutineStart.UNDISPATCHED) { repository.getEventPage(); returned = true }
            assertNotNull(server.takeRequest(5, TimeUnit.SECONDS))
            request.cancel()
            try { request.await(); fail("Cancellation must propagate") } catch (_: CancellationException) { }
            assertFalse(returned)
        } finally { server.shutdown() }
    }

}
