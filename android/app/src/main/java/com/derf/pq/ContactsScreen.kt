package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

data class ContactItem(val handle: String, val fingerprint: String, val isPaired: Boolean)

@Composable
fun ContactsComposeScreen() {
    var contactList by remember { mutableStateOf<List<ContactItem>>(emptyList()) }
    var newHandle by remember { mutableStateOf("") }
    var newKey by remember { mutableStateOf("") }
    var bannerStatus by remember { mutableStateOf("") }

    fun refreshContacts() {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val contactsObj = derf.callAttr("contacts_load")
            val keysList = contactsObj.callAttr("keys").asList()
            val list = mutableListOf<ContactItem>()
            for (keyObj in keysList) {
                val name = keyObj.toString()
                val valBytes = contactsObj.callAttr("get", name)
                val fpBytes = derf.callAttr("id_fp", valBytes)
                val fpHex = derf.callAttr("b64", fpBytes).toString().take(12)
                val sessFile = derf.callAttr("P", "lc_session_$name.json").toString()
                val isPaired = java.io.File(sessFile).exists()
                list.add(ContactItem(name, fpHex, isPaired))
            }
            contactList = list
        } catch (e: Exception) {
            bannerStatus = "Error loading contacts: ${e.message}"
        }
    }

    LaunchedEffect(Unit) {
        refreshContacts()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "CONTACT DIRECTORY & RATCHET STATUS",
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

        // Contact Cards List
        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(contactList) { item ->
                Surface(
                    color = CardSurface,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Person,
                                contentDescription = null,
                                tint = CrispWhite,
                                modifier = Modifier.padding(end = 12.dp)
                            )
                            Column {
                                Text(
                                    text = "${item.handle} ${if (item.isPaired) "[PAIRED]" else "[UNPAIRED]"}",
                                    color = if (item.isPaired) ActiveGreen else MutedText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 14.sp
                                )
                                Text(
                                    text = "FP: ${item.fingerprint}...",
                                    color = MutedText,
                                    fontSize = 12.sp
                                )
                            }
                        }

                        IconButton(
                            onClick = {
                                try {
                                    val py = Python.getInstance()
                                    val derf = py.getModule("Derf")
                                    derf.callAttr("contact_delete", item.handle)
                                    refreshContacts()
                                    bannerStatus = "Shredded contact '${item.handle}' and session state."
                                } catch (e: Exception) {
                                    bannerStatus = "Shred Error: ${e.message}"
                                }
                            }
                        ) {
                            Icon(
                                imageVector = Icons.Default.Delete,
                                contentDescription = "Shred Contact",
                                tint = ErrorRed
                            )
                        }
                    }
                }
            }
        }

        // Add Contact Form
        Text(
            text = "Add New Contact:",
            color = CrispWhite,
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 6.dp)
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = newHandle,
                onValueChange = { newHandle = it },
                placeholder = { Text("Handle", color = MutedText) },
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
                    .width(120.dp)
                    .height(52.dp)
            )

            OutlinedTextField(
                value = newKey,
                onValueChange = { newKey = it },
                placeholder = { Text("Paste Public Key...", color = MutedText) },
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
        }

        Button(
            onClick = {
                if (newHandle.isBlank() || newKey.isBlank()) {
                    bannerStatus = "Provide both Handle Name and Public Key."
                    return@Button
                }
                try {
                    val py = Python.getInstance()
                    val derf = py.getModule("Derf")
                    val pubBytes = derf.callAttr("parse_pubkey", newKey)
                    derf.callAttr("contact_add", newHandle, pubBytes)
                    newHandle = ""
                    newKey = ""
                    refreshContacts()
                    bannerStatus = "Contact saved successfully!"
                } catch (e: Exception) {
                    bannerStatus = "Invalid Key: ${e.message}"
                }
            },
            colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        ) {
            Text("SAVE CONTACT", fontWeight = FontWeight.Bold)
        }
    }
}
