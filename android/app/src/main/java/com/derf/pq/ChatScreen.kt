package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@Composable
fun ChatComposeScreen() {
    var activePeer by remember { mutableStateOf<String?>(null) }
    var chatTranscript by remember { mutableStateOf("Welcome to Derf PQ Messenger.\n[Select a contact in Contacts tab to begin chatting]\n") }
    var messageText by remember { mutableStateOf("") }
    var packetText by remember { mutableStateOf("") }
    var bannerStatus by remember { mutableStateOf("") }

    // Load active peer on entry
    LaunchedEffect(Unit) {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val contactsMap = derf.callAttr("contacts_load").asMap()
            if (contactsMap.isNotEmpty()) {
                activePeer = contactsMap.keys.first().toString()
            }
        } catch (e: Exception) {
            bannerStatus = "Error loading contacts: ${e.message}"
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        // Active Peer Header
        Text(
            text = if (activePeer != null) "Active Peer: $activePeer" else "Active Peer: [No Contact Selected]",
            color = ActiveGreen,
            fontSize = 15.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        // Chat Transcript Box
        Surface(
            color = CardSurface,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(bottom = 12.dp)
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(12.dp)
            ) {
                item {
                    Text(
                        text = chatTranscript,
                        color = CrispWhite,
                        fontSize = 14.sp
                    )
                }
            }
        }

        if (bannerStatus.isNotBlank()) {
            Text(
                text = bannerStatus,
                color = ElectricCyan,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }

        // Decryption Section
        Text(
            text = "Decrypt Received Ciphertext Packet:",
            color = ElectricCyan,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = packetText,
                onValueChange = { packetText = it },
                placeholder = { Text("Paste DERF:V1: packet here...", color = MutedText) },
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
                        val input = packetText.ifBlank { derf.callAttr("safe_paste").toString() }
                        if (input.contains("DERF:V1:")) {
                            val decrypted = derf.callAttr("decrypt_alien_stack", input, derf.get("idn")).toString()
                            if (decrypted.isNotBlank() && decrypted != "None") {
                                chatTranscript += "\n[Peer]: $decrypted\n"
                                packetText = ""
                                bannerStatus = "Decrypted Message: $decrypted"
                            } else {
                                bannerStatus = "Decryption Failed: Stale packet or session key error."
                            }
                        } else {
                            bannerStatus = "Provide a valid DERF:V1: packet."
                        }
                    } catch (e: Exception) {
                        bannerStatus = "Decryption Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.height(52.dp)
            ) {
                Text("DECRYPT", fontWeight = FontWeight.Bold)
            }
        }

        // Composer Section
        Text(
            text = "Compose Encrypted Message:",
            color = CrispWhite,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = messageText,
                onValueChange = { messageText = it },
                placeholder = { Text("Type confidential message...", color = MutedText) },
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
                    if (messageText.isBlank()) return@Button
                    if (activePeer == null) {
                        bannerStatus = "Error: Select a contact from Contacts tab first."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val cipherText = derf.callAttr("encrypt_alien_stack", messageText, activePeer, derf.get("idn")).toString()
                        if (cipherText.isNotBlank() && cipherText != "None") {
                            derf.callAttr("safe_copy", cipherText)
                            chatTranscript += "\n[Me -> $activePeer]: $messageText\n[Ciphertext copied to clipboard]\n"
                            messageText = ""
                            bannerStatus = "DERF Ciphertext copied to clipboard!"
                        } else {
                            bannerStatus = "Encryption Failed: Perform pairing first."
                        }
                    } catch (e: Exception) {
                        bannerStatus = "Encryption Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.height(52.dp)
            ) {
                Text("ENCRYPT", fontWeight = FontWeight.Bold)
            }
        }
    }
}
