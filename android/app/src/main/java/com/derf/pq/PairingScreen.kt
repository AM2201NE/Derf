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
fun PairingComposeScreen() {
    var activePeer by remember { mutableStateOf<String?>(null) }
    var bannerStatus by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val contactsMap = derf.callAttr("contacts_load").asMap()
            if (contactsMap.isNotEmpty()) {
                activePeer = contactsMap.keys.first().toString()
            }
        } catch (e: Exception) {
            bannerStatus = "Error: ${e.message}"
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "HANDSHAKE PAIRING STUDIO",
            color = ElectricCyan,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        Text(
            text = "Target Contact: ${activePeer ?: "[None Selected - Add Contact First]"}",
            color = CrispWhite,
            fontSize = 14.sp,
            modifier = Modifier.padding(bottom = 20.dp)
        )

        if (bannerStatus.isNotBlank()) {
            Text(
                text = bannerStatus,
                color = ElectricCyan,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 16.dp)
            )
        }

        Column(
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Step 1: Generate Invite
            Button(
                onClick = {
                    if (activePeer == null) {
                        bannerStatus = "Save and select a contact first."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val contacts = derf.callAttr("contacts_load").asMap()
                        val peerPub = contacts[activePeer]
                        val idn = derf.get("idn")
                        val res = derf.callAttr("hs_req", idn, peerPub)
                        val reqBlob = res.asList()[0]
                        val pend = res.asList()[1]
                        val pendPath = derf.callAttr("P", "lc_pending_$activePeer.json").toString()
                        derf.callAttr("vsave", pendPath, pend)
                        val invB64 = derf.callAttr("b64", reqBlob).toString()
                        derf.callAttr("safe_copy", invB64)
                        bannerStatus = "Handshake invite copied to clipboard! Send to $activePeer."
                    } catch (e: Exception) {
                        bannerStatus = "Invite Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("1. GENERATE & COPY INVITE", fontWeight = FontWeight.Bold)
            }

            // Step 2: Accept Invite
            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val invB64 = derf.callAttr("safe_paste").toString().trim()
                        if (invB64.isBlank()) {
                            bannerStatus = "Copy received invite code to clipboard first."
                            return@Button
                        }
                        val rawReq = derf.callAttr("ub64", invB64)
                        val idn = derf.get("idn")
                        val res = derf.callAttr("hs_rsp", idn, rawReq)
                        val rspBlob = res.asList()[0]
                        val peerPub = res.asList()[1]
                        val peerName = "Peer_" + derf.callAttr("b64", peerPub).toString().take(4)
                        derf.callAttr("contact_add", peerName, peerPub)
                        activePeer = peerName
                        val rspB64 = derf.callAttr("b64", rspBlob).toString()
                        derf.callAttr("safe_copy", rspB64)
                        val code = derf.callAttr("safety_code", derf.callAttr("id_fp", derf.callAttr("id_bundle", idn)), derf.callAttr("id_fp", peerPub)).toString()
                        bannerStatus = "Invite accepted & reply copied! Safety Code: $code"
                    } catch (e: Exception) {
                        bannerStatus = "Accept Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("2. ACCEPT INVITE FROM CLIPBOARD", fontWeight = FontWeight.Bold)
            }

            // Step 3: Complete Handshake
            Button(
                onClick = {
                    if (activePeer == null) {
                        bannerStatus = "Select contact handle to complete pairing."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val rspB64 = derf.callAttr("safe_paste").toString().trim()
                        if (rspB64.isBlank()) {
                            bannerStatus = "Copy received reply code to clipboard first."
                            return@Button
                        }
                        val rawRsp = derf.callAttr("ub64", rspB64)
                        val pendPath = derf.callAttr("P", "lc_pending_$activePeer.json").toString()
                        if (!java.io.File(pendPath).exists()) {
                            bannerStatus = "No pending handshake for $activePeer."
                            return@Button
                        }
                        val pend = derf.callAttr("vload", pendPath)
                        val idn = derf.get("idn")
                        derf.callAttr("hs_complete", idn, pend, rawRsp)
                        val contacts = derf.callAttr("contacts_load").asMap()
                        val peerPub = contacts[activePeer]
                        val code = derf.callAttr("safety_code", derf.callAttr("id_fp", derf.callAttr("id_bundle", idn)), derf.callAttr("id_fp", peerPub)).toString()
                        bannerStatus = "Double Ratchet active with $activePeer! Safety Code: $code"
                    } catch (e: Exception) {
                        bannerStatus = "Handshake Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("3. COMPLETE HANDSHAKE FROM REPLY", fontWeight = FontWeight.Bold)
            }
        }
    }
}
