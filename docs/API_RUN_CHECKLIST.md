# API Run Checklist

Generated from the local `results` folder in `C:\Users\TalalHussain\GitProjects\SIT-Automation`.

## Latest NBP CAS Run

Report file:

`results/results_cas_20260908_150822.json`

Summary:

| Metric | Count |
| --- | ---: |
| Total | 84 |
| Passed | 81 |
| Failed | 3 |
| Pass Percent | 96.43% |
| Expected Negative Passed | 52 |
| Negative Mismatch | 1 |
| Regression Failed | 2 |

Checklist:

| Done | API | Total | Passed | Failed |
| --- | --- | ---: | ---: | ---: |
| [x] | `authenticate` | 4 | 2 | 2 |
| [x] | `directposting` | 1 | 0 | 1 |
| [x] | `payment` | 79 | 79 | 0 |

## Latest NBP Failures

| TC ID | API | Current Result | Reason |
| --- | --- | --- | --- |
| `TC002` | `directposting` | Failed | API returned `00 SUCCESS`, but testcase expected `99`. This is an expected-response mapping issue. |
| `TC178` | `authenticate` | Failed | NBP run used `dib` credentials and received `401 Bad credentials`. |
| `TC179` | `authenticate` | Failed | NBP run used `dib` credentials and received `401 Bad credentials`. |

## All APIs Seen In Result History

These APIs have appeared in at least one local result report:

- [x] `alias`
- [x] `authenticate`
- [x] `backofficeUsingPOST`
- [x] `createAuthenticationTokenUsingPOST`
- [x] `creditAdvice`
- [x] `creditAdvice_1`
- [x] `creditAdvice_2`
- [x] `creditAdviceBackOffice`
- [x] `creditAdviceBatch`
- [x] `creditAdviceCommissionAggregator`
- [x] `creditAdviceOffUs`
- [x] `creditAdviceOnus`
- [x] `creditAdvicePosSettlement`
- [x] `defineDefaultAccount`
- [x] `deleteaccount`
- [x] `deletecustomer`
- [x] `delinkaccount`
- [x] `delinkAccountToAlias`
- [x] `directposting`
- [x] `DynamicQRC`
- [x] `generateRTP`
- [x] `generateRTPandDynamicQRC`
- [x] `getaliasinformation`
- [x] `getBatchDetailsUsingGET`
- [x] `getBatchUsingGET`
- [x] `getcustomerinformation`
- [x] `getdefaultaccount`
- [x] `getdefaultaccount->directposting`
- [x] `getDefaultAccountByAlias`
- [x] `getDefaultAccountByAliasRTP`
- [x] `getMerchantAliasesAndAccounts`
- [x] `getMerchantInfo`
- [x] `linkaccount`
- [x] `linkAccountToAlias`
- [x] `merchant_payment_alias`
- [x] `merchant_payment_direct_dqrc`
- [x] `merchant_payment_direct_rtpl`
- [x] `merchant_payment_direct_rtpn`
- [x] `merchant_payment_direct_sqrc`
- [x] `merchant_payment_sqrc`
- [x] `modify`
- [x] `onestep`
- [x] `oneStepDelete`
- [x] `payment`
- [x] `payment1`
- [x] `paymentInquiryDqrc`
- [x] `paymentInquiryUsingPOST`
- [x] `paymentInquiryV2UsingPOST`
- [x] `paymentUsingPOST`
- [x] `paymentUsingPOST_1`
- [x] `prevalInquiryUsingPOST`
- [x] `registerCustomer`
- [x] `registerMerchant`
- [x] `registerMerchantAccount`
- [x] `registerMerchantAlias`
- [x] `remittancedirectposting`
- [x] `remittancepayment`
- [x] `resendingPrevalOrPaymentUsingPOST`
- [x] `returnPayment`
- [x] `rtpCancelletion`
- [x] `rtpIdValidate`
- [x] `rtpInquiry`
- [x] `RTPLater`
- [x] `RTPNow`
- [x] `RTPPreApproved`
- [x] `titlefetch`
- [x] `titlefetch->directposting`
- [x] `titlefetchconv`
- [x] `titlefetchiban`
- [x] `titleFetchRTP`
- [x] `transaction`
- [x] `transaction_status`
- [x] `updateAccountStatus`
- [x] `updateAliasInfo`
- [x] `updateAliasStatus`
- [x] `updateCertificate`
- [x] `updateMerchantInfo`
- [x] `updateMerchantStatus`
- [x] `updatestatus`
- [x] `validateUsingPOST`

## Notes

- The latest NBP `payment` API run is clean: `79/79` passed.
- `TC002` should be treated as a testcase mapping correction because NBP returned a successful `00` response.
- `TC178` and `TC179` should not use DIB credentials for NBP. Either map them to NBP credentials or exclude those bank-specific DIB auth cases from the NBP testcase file.
