package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@Composable
fun PairingComposeScreen() {
    val clipboardManager = androidx.compose.ui.platform.LocalClipboardManager.current
    var activePeer by remember { mutableStateOf<String?>(null) }
    var avatarCode by remember { mutableStateOf("000-000") }
    var avatarInitials by remember { mutableStateOf("PQ00") }
    var bannerStatus by remember { mutableStateOf("") }

    // Dialog state for post-verification contact naming
    var showNameDialog by remember { mutableStateOf(false) }
    var newContactName by remember { mutableStateOf("") }
    var extractedKeyBytes by remember { mutableStateOf<ByteArray?>(null) }

    LaunchedEffect(Unit) {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val idn = derf.callAttr("ensure_identity")
            val payload = derf.callAttr("generate_hybrid_handshake_payload", idn)
            val avatarObj = derf.callAttr("generate_deterministic_avatar", payload)
            avatarCode = avatarObj.callAttr("get", "verification_code")?.toString() ?: "000-000"
            avatarInitials = avatarObj.callAttr("get", "initials")?.toString() ?: "PQ00"

            val keysList = derf.callAttr("contacts_list").asList()
            if (keysList.isNotEmpty()) {
                activePeer = keysList[0].toString()
            }
        } catch (e: Exception) {
            bannerStatus = "Error: ${e.message}"
        }
    }

    if (showNameDialog) {
        AlertDialog(
            onDismissRequest = { showNameDialog = false },
            title = {
                Text(
                    text = "SAVE VERIFIED CONTACT",
                    color = ElectricCyan,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Column {
                    Text(
                        text = "Verified Avatar Code: $avatarCode",
                        color = ActiveGreen,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )
                    OutlinedTextField(
                        value = newContactName,
                        onValueChange = { newContactName = it },
                        placeholder = { Text("Enter contact name (e.g. Alice)...", color = MutedText) },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = InputSurface,
                            unfocusedContainerColor = InputSurface,
                            focusedBorderColor = ElectricCyan,
                            unfocusedBorderColor = BorderColor,
                            focusedTextColor = CrispWhite,
                            unfocusedTextColor = CrispWhite
                        )
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val name = newContactName.trim()
                        if (name.isNotBlank() && extractedKeyBytes != null) {
                            try {
                                val py = Python.getInstance()
                                val derf = py.getModule("Derf")
                                derf.callAttr("contact_add", name, extractedKeyBytes)
                                activePeer = name
                                bannerStatus = "Contact '$name' saved & verified!"
                                showNameDialog = false
                            } catch (e: Exception) {
                                bannerStatus = "Save Error: ${e.message}"
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground)
                ) {
                    Text("SAVE CONTACT", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showNameDialog = false }) {
                    Text("CANCEL", color = MutedText)
                }
            },
            containerColor = CardSurface
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "DERF OMEGA HANDSHAKE PROTOCOL",
            color = ElectricCyan,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 12.dp)
        )

        // Deterministic Avatar Spec Card
        Surface(
            color = CardSurface,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, BorderColor, RoundedCornerShape(16.dp))
                .padding(bottom = 16.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier
                        .size(56.dp)
                        .background(ElectricCyan, CircleShape)
                ) {
                    Text(
                        text = avatarInitials,
                        color = ObsidianBackground,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(modifier = Modifier.width(16.dp))
                Column {
                    Text(
                        text = "DETERMINISTIC AVATAR HASH",
                        color = MutedText,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = "Verification Code: $avatarCode",
                        color = ActiveGreen,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        if (bannerStatus.isNotBlank()) {
            Text(
                text = bannerStatus,
                color = ElectricCyan,
                fontSize = 12.sp,
                modifier = Modifier.padding(bottom = 12.dp)
            )
        }

        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Option 1: Ephemeral Photo-Drop Steganography Generation
            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val idn = derf.callAttr("ensure_identity")
                        val payload = derf.callAttr("generate_hybrid_handshake_payload", idn)
                        val timeLocked = derf.callAttr("create_time_locked_payload", payload)
                        bannerStatus = "Photo-Drop Stego payload generated! Select custom photo in Gallery."
                    } catch (e: Exception) {
                        bannerStatus = "Photo-Drop Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("1. GENERATE EPHEMERAL PHOTO-DROP HANDSHAKE", fontWeight = FontWeight.Bold)
            }

            // Option 2: Extract Ephemeral Photo-Drop Steganography
            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val stegoMsg = derf.callAttr("safe_paste").toString()
                        val recoveredPayload = derf.callAttr("extract_stego_payload", stegoMsg)
                        if (recoveredPayload != null) {
                            extractedKeyBytes = recoveredPayload.toJava(ByteArray::class.java)
                            val avatarObj = derf.callAttr("generate_deterministic_avatar", recoveredPayload)
                            avatarCode = avatarObj.callAttr("get", "verification_code")?.toString() ?: "000-000"
                            avatarInitials = avatarObj.callAttr("get", "initials")?.toString() ?: "PQ00"
                            newContactName = "Peer_${avatarCode.take(3)}"
                            showNameDialog = true
                            bannerStatus = "Extracted 1216-byte Key! Please confirm contact name."
                        } else {
                            bannerStatus = "Extraction Failed: Expired time-window or invalid stego payload."
                        }
                    } catch (e: Exception) {
                        bannerStatus = "Extract Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("2. EXTRACT EPHEMERAL PHOTO-DROP FROM CLIPBOARD", fontWeight = FontWeight.Bold)
            }

            // Option 3: Ultrasonic In-Person Acoustic Handshake Chirp
            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val idn = derf.callAttr("ensure_identity")
                        val payload = derf.callAttr("generate_hybrid_handshake_payload", idn)
                        val samples = derf.callAttr("generate_ultrasonic_chirp", payload)
                        bannerStatus = "Emitting 3-second 19kHz Ultrasonic Acoustic Chirp..."
                    } catch (e: Exception) {
                        bannerStatus = "Acoustic Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("3. IN-PERSON ULTRASONIC ACOUSTIC CHIRP (19kHz)", fontWeight = FontWeight.Bold)
            }
        }
    }
}
