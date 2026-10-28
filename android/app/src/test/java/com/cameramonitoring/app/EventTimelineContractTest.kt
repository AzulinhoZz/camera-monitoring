package com.cameramonitoring.app

import com.cameramonitoring.app.data.model.EventListResponse
import com.cameramonitoring.app.data.remote.ApiService
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class EventTimelineContractTest {
    @Test fun legacyHistoryStillDecodesWithoutPagination() {
        val page = Gson().fromJson("""{"total":0,"events":[]}""", EventListResponse::class.java)
        assertTrue(page.events.isEmpty())
        assertFalse(page.hasMore)
        assertNull(page.nextCursor)
    }

    @Test fun filtersAndOpaqueCursorAreEncodedAsQueryParameters() = runBlocking {
        val server = MockWebServer()
        server.start()
        try {
            server.enqueue(MockResponse().setBody("""{"total":0,"events":[],"has_more":true,"next_cursor":"next==","summary":{"scope":"page"}}"""))
            val api = Retrofit.Builder().baseUrl(server.url("/"))
                .addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
            val response = api.getEvents("camera-fixture", "vision_intrusion", "pending", "2026-10-27T12:00:00Z", "opaque+/==", 30)
            assertTrue(response.isSuccessful)
            assertEquals("next==", response.body()!!.nextCursor)
            assertTrue(response.body()!!.hasMore)
            val url = server.takeRequest().requestUrl!!
            assertEquals("/events", url.encodedPath)
            assertEquals("camera-fixture", url.queryParameter("camera_id"))
            assertEquals("vision_intrusion", url.queryParameter("event_type"))
            assertEquals("pending", url.queryParameter("review_status"))
            assertEquals("2026-10-27T12:00:00Z", url.queryParameter("since"))
            assertEquals("opaque+/==", url.queryParameter("cursor"))
            assertEquals("30", url.queryParameter("limit"))
        } finally { server.shutdown() }
    }
}
