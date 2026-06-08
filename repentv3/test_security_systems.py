"""
Repent - Security Systems Test Script

Comprehensive test script for the new security systems:
- Multi-layer defense system
- Behavioral analysis and anomaly detection  
- Zero-trust architecture

This script validates that all components work correctly together.
"""

import asyncio
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, '.')

from utils.multi_layer_defense import (
    get_defense_system,
    SecurityContext,
    ThreatLevel,
    ResponseAction
)
from utils.behavioral_analysis import (
    get_behavioral_engine,
    AnomalyType
)
from utils.zero_trust import (
    get_zero_trust_engine,
    AccessRequest,
    AccessDecision,
    TrustLevel
)
from utils.logger import get_logger


class SecuritySystemsTester:
    """Test suite for security systems."""

    def __init__(self):
        self.logger = get_logger()
        self.defense_system = get_defense_system()
        self.behavioral_engine = get_behavioral_engine()
        self.zero_trust_engine = get_zero_trust_engine()
        
        self.test_results = []

    def log_test_result(self, test_name: str, passed: bool, details: str = ""):
        """Log a test result."""
        result = {
            'test_name': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now(timezone.utc)
        }
        self.test_results.append(result)
        
        status = "[PASS]" if passed else "[FAIL]"
        self.logger.info(f"{status}: {test_name} - {details}")

    async def test_multi_layer_defense(self):
        """Test multi-layer defense system."""
        self.logger.info("Testing Multi-Layer Defense System...")
        
        # Test 1: Normal user action
        try:
            context = SecurityContext(
                guild_id=123456789,
                user_id=987654321,
                action_type="message_send",
                additional_data={}
            )
            
            decision = await self.defense_system.analyze_event(context)
            
            passed = decision.overall_threat_level == ThreatLevel.SAFE
            self.log_test_result(
                "Multi-Layer: Normal action",
                passed,
                f"Threat level: {decision.overall_threat_level.name}"
            )
        except Exception as e:
            self.log_test_result("Multi-Layer: Normal action", False, str(e))
        
        # Test 2: Suspicious action pattern
        try:
            # Simulate multiple rapid actions
            for i in range(20):
                context = SecurityContext(
                    guild_id=123456789,
                    user_id=987654322,  # Different user
                    action_type="ban",
                    additional_data={}
                )
                await self.defense_system.analyze_event(context)
            
            # Test the last one
            decision = await self.defense_system.analyze_event(context)
            
            # Should at least detect some elevated threat level
            passed = decision.overall_threat_level in [ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]
            self.log_test_result(
                "Multi-Layer: Rapid suspicious actions",
                passed,
                f"Threat level: {decision.overall_threat_level.name} (detected elevated activity)"
            )
        except Exception as e:
            self.log_test_result("Multi-Layer: Rapid suspicious actions", False, str(e))
        
        # Test 3: Get statistics
        try:
            stats = self.defense_system.get_statistics()
            passed = stats['total_analyses'] > 0
            self.log_test_result(
                "Multi-Layer: Statistics",
                passed,
                f"Total analyses: {stats['total_analyses']}"
            )
        except Exception as e:
            self.log_test_result("Multi-Layer: Statistics", False, str(e))

    async def test_behavioral_analysis(self):
        """Test behavioral analysis system."""
        self.logger.info("Testing Behavioral Analysis System...")
        
        # Test 1: Normal user behavior
        try:
            report = await self.behavioral_engine.analyze_user_action(
                guild_id=123456789,
                user_id=987654323,
                action_type="message_send"
            )
            
            passed = report.overall_score < 0.3  # Should be low anomaly
            self.log_test_result(
                "Behavioral: Normal user action",
                passed,
                f"Anomaly score: {report.overall_score:.2f}"
            )
        except Exception as e:
            self.log_test_result("Behavioral: Normal user action", False, str(e))
        
        # Test 2: High-velocity actions
        try:
            # Simulate rapid actions
            for i in range(50):
                await self.behavioral_engine.analyze_user_action(
                    guild_id=123456789,
                    user_id=987654324,
                    action_type="ban"
                )
            
            report = await self.behavioral_engine.analyze_user_action(
                guild_id=123456789,
                user_id=987654324,
                action_type="ban"
            )
            
            passed = report.overall_score > 0.5  # Should detect anomaly
            self.log_test_result(
                "Behavioral: High-velocity detection",
                passed,
                f"Anomaly score: {report.overall_score:.2f}"
            )
        except Exception as e:
            self.log_test_result("Behavioral: High-velocity detection", False, str(e))
        
        # Test 3: Get user profile
        try:
            profile = self.behavioral_engine.get_user_profile(987654323)
            passed = profile is not None and profile.total_actions > 0
            self.log_test_result(
                "Behavioral: User profile retrieval",
                passed,
                f"Profile actions: {profile.total_actions if profile else 0}"
            )
        except Exception as e:
            self.log_test_result("Behavioral: User profile retrieval", False, str(e))

    async def test_zero_trust(self):
        """Test zero-trust architecture."""
        self.logger.info("Testing Zero-Trust Architecture...")
        
        # Test 1: Normal access request
        try:
            request = AccessRequest(
                user_id=987654325,
                guild_id=123456789,
                action_type="message_send"
            )
            
            response = await self.zero_trust_engine.evaluate_access(request)
            
            passed = response.decision in [AccessDecision.ALLOW, AccessDecision.ALLOW_WITH_MONITORING]
            self.log_test_result(
                "Zero-Trust: Normal access request",
                passed,
                f"Decision: {response.decision.value}"
            )
        except Exception as e:
            self.log_test_result("Zero-Trust: Normal access request", False, str(e))
        
        # Test 2: Critical action without trust
        try:
            request = AccessRequest(
                user_id=987654326,  # New user with no history
                guild_id=123456789,
                action_type="ban"  # Critical action
            )
            
            response = await self.zero_trust_engine.evaluate_access(request)
            
            passed = response.decision in [AccessDecision.DENY, AccessDecision.ALLOW_WITH_VERIFICATION]
            self.log_test_result(
                "Zero-Trust: Critical action without trust",
                passed,
                f"Decision: {response.decision.value}, Trust score: {response.trust_score.overall_score:.2f}"
            )
        except Exception as e:
            self.log_test_result("Zero-Trust: Critical action without trust", False, str(e))
        
        # Test 3: Trust score manipulation
        try:
            self.zero_trust_engine.update_trust_score(987654325, 123456789, 0.3)
            trust_score = self.zero_trust_engine.get_trust_score(987654325, 123456789)
            
            passed = trust_score is not None and trust_score.overall_score > 0
            score_value = f"{trust_score.overall_score:.2f}" if trust_score else "0"
            self.log_test_result(
                "Zero-Trust: Trust score manipulation",
                passed,
                f"Trust score: {score_value}"
            )
        except Exception as e:
            self.log_test_result("Zero-Trust: Trust score manipulation", False, str(e))
        
        # Test 4: Session management
        try:
            token = await self.zero_trust_engine.create_session_token(
                user_id=987654325,
                guild_id=123456789
            )
            
            is_valid = await self.zero_trust_engine.verify_session(token)
            
            passed = is_valid
            self.log_test_result(
                "Zero-Trust: Session token creation and verification",
                passed,
                f"Token valid: {is_valid}"
            )
        except Exception as e:
            self.log_test_result("Zero-Trust: Session token creation and verification", False, str(e))
        
        # Test 5: Get statistics
        try:
            stats = self.zero_trust_engine.get_statistics()
            passed = stats['total_trust_scores'] > 0
            self.log_test_result(
                "Zero-Trust: Statistics",
                passed,
                f"Total trust scores: {stats['total_trust_scores']}"
            )
        except Exception as e:
            self.log_test_result("Zero-Trust: Statistics", False, str(e))

    async def test_integration(self):
        """Test integration between systems."""
        self.logger.info("Testing System Integration...")
        
        # Test 1: End-to-end security evaluation
        try:
            guild_id = 123456789
            user_id = 987654327
            action_type = "ban"
            
            # Create security context
            context = SecurityContext(
                guild_id=guild_id,
                user_id=user_id,
                action_type=action_type
            )
            
            # Run through multi-layer defense
            defense_decision = await self.defense_system.analyze_event(context)
            
            # Run behavioral analysis
            anomaly_report = await self.behavioral_engine.analyze_user_action(
                guild_id, user_id, action_type
            )
            
            # Run zero-trust evaluation
            access_request = AccessRequest(
                user_id=user_id,
                guild_id=guild_id,
                action_type=action_type
            )
            zero_trust_response = await self.zero_trust_engine.evaluate_access(access_request)
            
            # All systems should produce results
            passed = (
                defense_decision.decision_id is not None and
                anomaly_report.overall_score >= 0 and
                zero_trust_response.request_id is not None
            )
            
            self.log_test_result(
                "Integration: End-to-end security evaluation",
                passed,
                f"Defense: {defense_decision.overall_threat_level.name}, "
                f"Anomaly: {anomaly_report.overall_score:.2f}, "
                f"Zero-Trust: {zero_trust_response.decision.value}"
            )
        except Exception as e:
            self.log_test_result("Integration: End-to-end security evaluation", False, str(e))

    async def run_all_tests(self):
        """Run all security system tests."""
        self.logger.info("=" * 50)
        self.logger.info("Starting Security Systems Test Suite")
        self.logger.info("=" * 50)
        
        await self.test_multi_layer_defense()
        await self.test_behavioral_analysis()
        await self.test_zero_trust()
        await self.test_integration()
        
        self.logger.info("=" * 50)
        self.logger.info("Test Suite Completed")
        self.logger.info("=" * 50)
        
        # Print summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Passed: {passed_tests}")
        self.logger.info(f"Failed: {failed_tests}")
        self.logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        return failed_tests == 0


async def main():
    """Main test runner."""
    tester = SecuritySystemsTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())