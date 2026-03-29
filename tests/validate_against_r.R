# tests/validate_against_r.R
# Compare MetaReproducer DL/REML against metafor::rma()
# Run: Rscript tests/validate_against_r.R
# Output: JSON block with reference values for Python cross-validation

library(metafor)

cat("=== MetaReproducer R Validation (Extended) ===\n\n")

results <- list()

# --- Test 1: 5 binary studies (from conftest.py fixture) ---
yi1 <- c(log(0.75), log(0.80), log(0.90), log(0.70), log(0.85))
sei1 <- c(0.20, 0.25, 0.30, 0.15, 0.22)

dl1 <- rma(yi1, sei1^2, method="DL")
reml1 <- rma(yi1, sei1^2, method="REML")

cat("Test 1: 5 binary studies\n")
cat(sprintf("  DL   pooled=%.10f  tau2=%.10f  I2=%.4f  Q=%.6f\n",
            dl1$beta, dl1$tau2, dl1$I2, dl1$QE))
cat(sprintf("  REML pooled=%.10f  tau2=%.10f  I2=%.4f\n",
            reml1$beta, reml1$tau2, reml1$I2))

results$test1_dl_pooled <- as.numeric(dl1$beta)
results$test1_dl_tau2 <- dl1$tau2
results$test1_dl_i2 <- dl1$I2
results$test1_dl_q <- dl1$QE
results$test1_dl_se <- dl1$se
results$test1_dl_ci_lower <- dl1$ci.lb
results$test1_dl_ci_upper <- dl1$ci.ub
results$test1_reml_pooled <- as.numeric(reml1$beta)
results$test1_reml_tau2 <- reml1$tau2
results$test1_reml_se <- reml1$se

# --- Test 2: Homogeneous (3 identical studies) ---
yi2 <- rep(log(0.80), 3)
sei2 <- rep(0.20, 3)
dl2 <- rma(yi2, sei2^2, method="DL")
cat(sprintf("\nTest 2: Homogeneous (DL tau2=%.10f  pooled=%.10f)\n",
            dl2$tau2, dl2$beta))

results$test2_dl_pooled <- as.numeric(dl2$beta)
results$test2_dl_tau2 <- dl2$tau2

# --- Test 3: k=2 ---
yi3 <- c(log(0.5), log(1.5))
sei3 <- c(0.2, 0.2)
dl3 <- rma(yi3, sei3^2, method="DL")
cat(sprintf("\nTest 3: k=2 (DL pooled=%.10f  tau2=%.10f)\n",
            dl3$beta, dl3$tau2))

results$test3_dl_pooled <- as.numeric(dl3$beta)
results$test3_dl_tau2 <- dl3$tau2

# --- Test 4: Large heterogeneity ---
yi4 <- c(-1.5, -0.2, 0.8, -0.5, 0.3, -1.0, 0.1, -0.7)
sei4 <- c(0.3, 0.15, 0.25, 0.20, 0.35, 0.18, 0.22, 0.28)
dl4 <- rma(yi4, sei4^2, method="DL")
reml4 <- rma(yi4, sei4^2, method="REML")
cat(sprintf("\nTest 4: Large heterogeneity (k=8)\n"))
cat(sprintf("  DL   pooled=%.10f  tau2=%.10f  I2=%.4f\n",
            dl4$beta, dl4$tau2, dl4$I2))
cat(sprintf("  REML pooled=%.10f  tau2=%.10f  I2=%.4f\n",
            reml4$beta, reml4$tau2, reml4$I2))

results$test4_dl_pooled <- as.numeric(dl4$beta)
results$test4_dl_tau2 <- dl4$tau2
results$test4_dl_i2 <- dl4$I2
results$test4_reml_pooled <- as.numeric(reml4$beta)
results$test4_reml_tau2 <- reml4$tau2
results$test4_reml_i2 <- reml4$I2

# --- Test 5: Continuous outcomes (MD-like) ---
yi5 <- c(-2.5, -3.1, -1.8, -2.9, -2.2, -3.5)
sei5 <- c(0.8, 1.0, 0.6, 0.9, 0.7, 1.2)
dl5 <- rma(yi5, sei5^2, method="DL")
reml5 <- rma(yi5, sei5^2, method="REML")
cat(sprintf("\nTest 5: Continuous (MD, k=6)\n"))
cat(sprintf("  DL   pooled=%.10f  tau2=%.10f  I2=%.4f\n",
            dl5$beta, dl5$tau2, dl5$I2))
cat(sprintf("  REML pooled=%.10f  tau2=%.10f\n",
            reml5$beta, reml5$tau2))

results$test5_dl_pooled <- as.numeric(dl5$beta)
results$test5_dl_tau2 <- dl5$tau2
results$test5_dl_i2 <- dl5$I2
results$test5_reml_pooled <- as.numeric(reml5$beta)
results$test5_reml_tau2 <- reml5$tau2

# --- Test 6: k=1 ---
dl6 <- rma(log(0.75), 0.20^2, method="DL")
cat(sprintf("\nTest 6: k=1 (pooled=%.10f  tau2=%.10f)\n",
            dl6$beta, dl6$tau2))

results$test6_dl_pooled <- as.numeric(dl6$beta)
results$test6_dl_tau2 <- dl6$tau2

# --- Test 7: Near-zero tau2 (all effects similar) ---
yi7 <- c(-0.30, -0.31, -0.29, -0.305, -0.295)
sei7 <- c(0.10, 0.12, 0.11, 0.09, 0.13)
dl7 <- rma(yi7, sei7^2, method="DL")
reml7 <- rma(yi7, sei7^2, method="REML")
cat(sprintf("\nTest 7: Near-zero tau2\n"))
cat(sprintf("  DL   pooled=%.10f  tau2=%.10f  I2=%.4f\n",
            dl7$beta, dl7$tau2, dl7$I2))
cat(sprintf("  REML pooled=%.10f  tau2=%.10f\n",
            reml7$beta, reml7$tau2))

results$test7_dl_pooled <- as.numeric(dl7$beta)
results$test7_dl_tau2 <- dl7$tau2
results$test7_reml_pooled <- as.numeric(reml7$beta)
results$test7_reml_tau2 <- reml7$tau2

# --- Output JSON reference values ---
cat("\n--- JSON ---\n")
cat(jsonlite::toJSON(results, auto_unbox=TRUE, digits=12))
cat("\n")
