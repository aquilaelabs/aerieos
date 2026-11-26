// What the app holds a dashboard's https address to (R290): learned once,
// at sign-in, and every later connection held to it. Where the system's
// authorities vouch for the address's name (a Let's Encrypt hostname, an
// edge in front), that is the check, as a browser's is. Otherwise the
// dashboard's own key: the pin of the public key its certificate carries,
// "sha256//" and the base64 of the sha256 of the key's SubjectPublicKeyInfo,
// the very form the controller prints on its console at every start and the
// Enroll dialog's command carries. A certificate the dashboard remakes over
// the same key passes; a machine in the middle with another key is refused.
package org.aerieos.app

import android.util.Base64
import java.net.URL
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

object Pins {
    /** The authorities' word for the name: no pin of the app's own. */
    const val CA = "ca"
    private const val KEY = "sha256//"

    /** A certificate's key, as a pin. */
    fun of(cert: X509Certificate): String =
        KEY + Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(cert.publicKey.encoded), Base64.NO_WRAP)

    /** A connection held to `pin`: a key's pin is the whole check (the
     *  address may be a bare IP, which no certificate of a LAN box names);
     *  the authorities' word, or none over http, leaves the platform's own. */
    fun hold(c: HttpsURLConnection, pin: String) {
        if (!pin.startsWith(KEY)) return
        c.sslSocketFactory = factory { seen ->
            if (seen != pin) throw CertificateException(
                "this dashboard's key is not the one this phone signed in to: sign in again where it was changed on purpose")
        }
        c.hostnameVerifier = HostnameVerifier { _, session ->
            (session.peerCertificates.firstOrNull() as? X509Certificate)?.let { of(it) == pin } ?: false
        }
    }

    private fun factory(check: (String) -> Unit): SSLSocketFactory {
        val tm = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
                throw CertificateException("the app presents no certificate of its own")
            }
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                if (chain.isEmpty()) throw CertificateException("the dashboard presented no certificate")
                check(of(chain[0]))
            }
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        return SSLContext.getInstance("TLS").apply { init(null, arrayOf<TrustManager>(tm), null) }.socketFactory
    }

    /** What to hold `base` to from now on, asked once as the person signs
     *  in: CA where the platform's authorities take the certificate for the
     *  name, else the key it presents now, "" over plain http. Blocking. */
    fun learn(base: String): String {
        val url = URL(base.trimEnd('/') + "/api/meta")
        if (url.protocol != "https") return ""
        try {
            (url.openConnection() as HttpsURLConnection).run {
                connectTimeout = 15_000; readTimeout = 15_000
                connect(); disconnect()
            }
            return CA
        } catch (e: SSLException) {
            // Not by the authorities: a dashboard's own certificate. Its key
            // is what the phone keeps, met here for the first time.
        }
        var seen = ""
        (url.openConnection() as HttpsURLConnection).run {
            connectTimeout = 15_000; readTimeout = 15_000
            sslSocketFactory = factory { seen = it }
            hostnameVerifier = HostnameVerifier { _, session ->
                (session.peerCertificates.firstOrNull() as? X509Certificate)?.let { of(it) == seen } ?: false
            }
            connect(); disconnect()
        }
        return seen
    }
}
