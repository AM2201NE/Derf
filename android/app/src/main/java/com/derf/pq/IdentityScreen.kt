package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@Composable
fun IdentityComposeScreen(onLock: () -> Unit) {
    var pkB64 by remember { mutableStateOf("") }
    var fpHex by remember { mutableStateOf("") }
    var safetyCode by remember { mutableStateOf("") }
    var freshSecs by remember { mutableStateOf("420") }
    var bannerStatus by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val idn = derf.get("idn")
            if (idn != null) {
                val bundle = derf.callAttr("id_bundle", idn)
                pkB64 = derf.callAttr("b64", bundle).toString()
                fpHex = derf.callAttr("b64", derf.callAttr("id_fp", bundle)).toString().take(24)
                freshSecs = derf.get("FRESH").toString()

                val keysList = derf.callAttr("contacts_list").asList()
                val contactsObj = derf.callAttr("contacts_load")
                if (keysList.isNotEmpty()) {
                    val peer = keysList[0].toString()
                    val peerPub = contactsObj.callAttr("get", peer)
                    safetyCode = derf.callAttr("safety_code", derf.callAttr("id_fp", bundle), derf.callAttr("id_fp", peerPub)).toString()
                }
            }
        } catch (e: Exception) {
            bannerStatus = "Error loading identity: ${e.message}"
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "MY IDENTITY & SETTINGS",
            color = ElectricCyan,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 12.dp)
        )

        if (bannerStatus.isNotBlank()) {
            Text(
                text = bannerStatus,
                color = ElectricCyan,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }

        // Identity Spec Box
        Surface(
            color = CardSurface,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(bottom = 12.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(12.dp)
            ) {
                Text(
                    text = "Public Key Bundle:\n$pkB64\n\nIdentity Fingerprint:\n$fpHex...\n\nOut-Of-Band Safety Code:\n${safetyCode.ifBlank { "[Select contact in Contacts tab]" }}",
                    color = CrispWhite,
                    fontSize = 13.sp
                )
            }
        }

        Button(
            onClick = {
                try {
                    val py = Python.getInstance()
                    val derf = py.getModule("Derf")
                    derf.callAttr("safe_copy", pkB64)
                    bannerStatus = "Public Key Bundle copied to clipboard!"
                } catch (e: Exception) {
                    bannerStatus = "Copy Error: ${e.message}"
                }
            },
            colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .padding(bottom = 12.dp)
        ) {
            Text("COPY MY PUBLIC KEY BUNDLE", fontWeight = FontWeight.Bold)
        }

        // Freshness Config Row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = freshSecs,
                onValueChange = { freshSecs = it },
                label = { Text("Freshness Tolerance (Secs)", color = MutedText) },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = InputSurface,
                    unfocusedContainerColor = InputSurface,
                    focusedBorderColor = ElectricCyan,
                    unfocusedBorderColor = BorderColor,
                    focusedTextColor = CrispWhite,
                    unfocusedTextColor = CrispWhite
                ),
                modifier = Modifier
                    .weight(1f)
                    .height(52.dp)
            )

            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val valFloat = freshSecs.toFloat()
                        derf.put("FRESH", valFloat)
                        bannerStatus = "Freshness limit updated to ${valFloat.toInt()}s!"
                    } catch (e: Exception) {
                        bannerStatus = "Invalid number: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.height(52.dp)
            ) {
                Text("SAVE", fontWeight = FontWeight.Bold)
            }
        }

        // Global Nuke Button
        Button(
            onClick = {
                try {
                    val py = Python.getInstance()
                    val derf = py.getModule("Derf")
                    derf.callAttr("nuke_all_files")
                    onLock()
                } catch (e: Exception) {
                    bannerStatus = "Nuke Error: ${e.message}"
                }
            },
            colors = ButtonDefaults.buttonColors(containerColor = ErrorRed, contentColor = CrispWhite),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        ) {
            Text("💣 NUKE ALL LOCAL DATA", fontWeight = FontWeight.Bold)
        }
    }
}
