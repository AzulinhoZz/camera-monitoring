package com.cameramonitoring.app

import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.model.SessionData
import com.cameramonitoring.app.data.remote.TokenAuthenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class InMemorySessionManager : SessionManager() {
    @Volatile var token: String? = "expired_access_token"
    @Volatile var refreshTokenStr: String? = "valid_refresh_token"
    @Volatile var clearSessionCalled = false
    @Volatile var savedAccessToken: String? = null

    override fun getAccessToken(): String? = token

    override fun getSession(): SessionData? {
        val t = token ?: return null
        return SessionData(t, refreshTokenStr, "user_123", "admin@cameramonitoring.com")
    }

    override fun saveSession(accessToken: String, refreshToken: String?, userId: String, userEmail: String?) {
        this.token = accessToken
        this.refreshTokenStr = refreshToken
        this.savedAccessToken = accessToken
    }

    override fun clearSession() {
        this.token = null
        this.refreshTokenStr = null
        this.clearSessionCalled = true
    }
}

class TokenAuthenticatorTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var sessionManager: InMemorySessionManager
    private var sessionExpiredCalled = false

    @Before
    fun setUp() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        sessionManager = InMemorySessionManager()
        sessionExpiredCalled = false
    }

    @After
    fun tearDown() {
        mockWebServer.shutdown()
    }

    @Test
    fun testTokenVigente() {
        mockWebServer.enqueue(MockResponse().setResponseCode(200).setBody("""{"status":"ok"}"""))

        val baseUrl = mockWebServer.url("/").toString()
        val authenticator = TokenAuthenticator(sessionManager, baseUrl) { sessionExpiredCalled = true }

        val client = OkHttpClient.Builder()
            .authenticator(authenticator)
            .build()

        val request = Request.Builder()
            .url(mockWebServer.url("/cameras"))
            .header("Authorization", "Bearer expired_access_token")
            .build()

        val response = client.newCall(request).execute()

        assertEquals(200, response.code)
        assertFalse(sessionExpiredCalled)
        assertEquals(1, mockWebServer.requestCount)
    }

    @Test
    fun testTokenCaducadoRenovacionExitosa() {
        // 1st request -> 401
        mockWebServer.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Token expirado"}"""))

        // Refresh request -> 200 with new token
        mockWebServer.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{
                    "access_token": "new_refreshed_token",
                    "refresh_token": "new_refresh_token",
                    "user": {"id": "user_123", "email": "admin@cameramonitoring.com"}
                }"""
            )
        )

        // Retry original request -> 200
        mockWebServer.enqueue(MockResponse().setResponseCode(200).setBody("""{"cameras":[]}"""))

        val baseUrl = mockWebServer.url("/").toString()
        val authenticator = TokenAuthenticator(sessionManager, baseUrl) { sessionExpiredCalled = true }

        val client = OkHttpClient.Builder()
            .authenticator(authenticator)
            .build()

        val request = Request.Builder()
            .url(mockWebServer.url("/cameras"))
            .header("Authorization", "Bearer expired_access_token")
            .build()

        val response = client.newCall(request).execute()

        assertEquals(200, response.code)
        assertFalse(sessionExpiredCalled)
        assertEquals("new_refreshed_token", sessionManager.savedAccessToken)
    }

    @Test
    fun testRenovacionFallida() {
        // 1st request -> 401
        mockWebServer.enqueue(MockResponse().setResponseCode(401))
        // Refresh request -> 401
        mockWebServer.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Refresh token expirado"}"""))

        val baseUrl = mockWebServer.url("/").toString()
        val authenticator = TokenAuthenticator(sessionManager, baseUrl) { sessionExpiredCalled = true }

        val client = OkHttpClient.Builder()
            .authenticator(authenticator)
            .build()

        val request = Request.Builder()
            .url(mockWebServer.url("/cameras"))
            .header("Authorization", "Bearer expired_access_token")
            .build()

        val response = client.newCall(request).execute()

        assertEquals(401, response.code)
        assertTrue(sessionExpiredCalled)
        assertTrue(sessionManager.clearSessionCalled)
    }

    @Test
    fun testLogin401NoDisparaRenovacion() {
        // Login request returns 401
        mockWebServer.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Credenciales inválidas"}"""))

        val baseUrl = mockWebServer.url("/").toString()
        val authenticator = TokenAuthenticator(sessionManager, baseUrl) { sessionExpiredCalled = true }

        val client = OkHttpClient.Builder()
            .authenticator(authenticator)
            .build()

        val request = Request.Builder()
            .url(mockWebServer.url("/auth/login"))
            .post("""{"email":"test@test.com","password":"wrong"}""".toRequestBody())
            .build()

        val response = client.newCall(request).execute()

        assertEquals(401, response.code)
        assertFalse(sessionExpiredCalled)
        assertEquals(1, mockWebServer.requestCount)
    }

    @Test
    fun testMultiplePeticionesSimultaneas() {
        // Enqueue 2 initial 401 responses for 2 concurrent requests
        mockWebServer.enqueue(MockResponse().setResponseCode(401))
        mockWebServer.enqueue(MockResponse().setResponseCode(401))

        // Enqueue ONLY 1 refresh response
        mockWebServer.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{
                    "access_token": "new_refreshed_token_concurrent",
                    "refresh_token": "new_refresh_token",
                    "user": {"id": "user_123", "email": "admin@cameramonitoring.com"}
                }"""
            )
        )

        // Enqueue 2 retry success responses
        mockWebServer.enqueue(MockResponse().setResponseCode(200).setBody("""{"cameras":[]}"""))
        mockWebServer.enqueue(MockResponse().setResponseCode(200).setBody("""{"cameras":[]}"""))

        val baseUrl = mockWebServer.url("/").toString()
        val authenticator = TokenAuthenticator(sessionManager, baseUrl) { sessionExpiredCalled = true }

        val client = OkHttpClient.Builder()
            .authenticator(authenticator)
            .build()

        val executor = Executors.newFixedThreadPool(2)

        val task1 = Callable {
            val req = Request.Builder()
                .url(mockWebServer.url("/cameras"))
                .header("Authorization", "Bearer expired_access_token")
                .build()
            client.newCall(req).execute()
        }

        val task2 = Callable {
            val req = Request.Builder()
                .url(mockWebServer.url("/events"))
                .header("Authorization", "Bearer expired_access_token")
                .build()
            client.newCall(req).execute()
        }

        val future1 = executor.submit(task1)
        val future2 = executor.submit(task2)

        val resp1 = future1.get(5, TimeUnit.SECONDS)
        val resp2 = future2.get(5, TimeUnit.SECONDS)

        executor.shutdown()
        assertEquals(200, resp1.code)
        assertEquals(200, resp2.code)
        assertFalse(sessionExpiredCalled)
    }
}
