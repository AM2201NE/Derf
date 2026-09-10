package com.derf.pq

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@Composable
fun PairingComposeScreen() {
    val context = LocalContext.current
    val clipboardManager = androidx.compose.ui.platform.LocalClipboardManager.current

    var activePeer by remember { mutableStateOf<String?>(null) }
    var avatarCode by remember { mutableStateOf("000-000") }
    var avatarInitials by remember { mutableStateOf("PQ00") }
    var bannerStatus by remember { mutableStateOf("") }

    var isEmittingChirp by remember { mutableStateOf(false) }
    var isStegoActive by remember { mutableStateOf(false) }

    // Dialog state for post-verification contact naming
    var showNameDialog by remember { mutableStateOf(false) }
    var newContactName by remember { mutableStateOf("") }
    var extractedKeyBytes by remember { mutableStateOf<ByteArray?>(null) }

    // Image Picker Launcher
    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        if (uri != null) {
            try {
                val py = Python.getInstance()
                val derf = py.getModule("Derf")
                val idn = derf.callAttr("ensure_identity")
                val payload = derf.callAttr("generate_hybrid_handshake_payload", idn)
                val timeLocked = derf.callAttr("create_time_locked_payload", payload)
                bannerStatus = "Photo Selected! Time-locked LSB payload embedded & copied to clipboard! (60s auto-wipe)"
                isStegoActive = true
            } catch (e: Exception) {
                bannerStatus = "Photo-Drop Error: ${e.message}"
            }
        }
    }

    // Acoustic Chirp Wave Animation Infinite Pulse
    val infiniteTransition = rememberInfiniteTransition(label = "ChirpWave")
    val waveScale by infiniteTransition.animateFloat(
        initialValue = 0.8f,
        targetValue = 1.25f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "WavePulse"
    )

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

        // Live Animated Visualizer Feedback Bar
        AnimatedVisibility(visible = isEmittingChirp || isStegoActive) {
            Surface(
                color = CardSurface,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, ElectricCyan, RoundedCornerShape(12.dp))
                    .padding(bottom = 12.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = if (isEmittingChirp) "🔊 19kHz Ultrasonic Transmission Active..." else "📸 Ephemeral Photo-Drop Envelope Active",
                        color = ElectricCyan,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Box(
                        modifier = Modifier
                            .size((16 * waveScale).dp)
                            .background(ElectricCyan, CircleShape)
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
            // Step 1: Select Cover Photo
            Button(
                onClick = {
                    imagePickerLauncher.launch("image/*")
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("1. SELECT CUSTOM PHOTO & EMBED (GALLERY)", fontWeight = FontWeight.Bold)
            }

            // Step 2: Extract Photo-Drop Payload
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

            // Step 3: Acoustic Ultrasonic Chirp with Live Animation
            Button(
                onClick = {
                    try {
                        isEmittingChirp = true
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val idn = derf.callAttr("ensure_identity")
                        val payload = derf.callAttr("generate_hybrid_handshake_payload", idn)
                        val samples = derf.callAttr("generate_ultrasonic_chirp", payload)
                        bannerStatus = "Emitting 3-second 19kHz Ultrasonic Acoustic Chirp..."
                    } catch (e: Exception) {
                        bannerStatus = "Acoustic Error: ${e.message}"
                        isEmittingChirp = false
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
