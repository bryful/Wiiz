#pragma once
#include <cstdint>
#include <string>
#include <vector>

std::string encodeBattery(const std::vector<uint8_t>& bytes, int scenario, const std::string& sha);
std::vector<uint8_t> decodeBattery(const std::string& text, int scenario, const std::string& sha);

// Reuse the original-format checksum/mirror reconstruction for binary SRAM too.
void repairBattery(std::vector<uint8_t>& bytes, int scenario);

// Whole-record exchange adapted from WizData.SwapChar (MIT).
void swapRosterRecords(std::vector<uint8_t>& bytes, int scenario, unsigned first, unsigned second);
